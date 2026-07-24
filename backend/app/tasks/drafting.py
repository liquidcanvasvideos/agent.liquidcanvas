"""
Drafting task - STEP 6 of strict pipeline
Generates email drafts using Gemini
"""
import asyncio
import json
import logging
from uuid import UUID
from sqlalchemy import select, and_, or_, func, update, text

from app.db.database import AsyncSessionLocal
from app.models.prospect import Prospect, ScrapeStatus, DraftStatus, ProspectStage
from app.models.job import Job
from app.clients.gemini import GeminiClient

logger = logging.getLogger(__name__)


def _coerce_json_value(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {}
    return {}


async def _job_progress_columns_exist(db) -> bool:
    result = await db.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'jobs'
            AND column_name IN ('drafts_created', 'total_targets')
            """
        )
    )
    existing_columns = {row[0] for row in result.fetchall()}
    return "drafts_created" in existing_columns and "total_targets" in existing_columns


def _has_complete_draft(prospect: Prospect) -> bool:
    subject = prospect.draft_subject or ""
    body = prospect.draft_body or ""
    return bool(subject.strip()) and bool(body.strip())


async def draft_prospects_async(job_id: str):
    """
    Generate email drafts for leads and scraped emails using Gemini
    
    BACKGROUND JOB MODE:
    - Queries prospects in background (eligibility check happens here)
    - Updates progress incrementally (drafts_created, total_targets)
    - Sets draft_status = "drafted" for each prospect
    """
    async with AsyncSessionLocal() as db:
        try:
            try:
                job_uuid = UUID(job_id)
            except Exception as e:
                logger.error(f"❌ [DRAFTING] Invalid job id {job_id}: {e}")
                return {"error": "Invalid job ID"}

            has_progress_columns = await _job_progress_columns_exist(db)
            job = None
            job_params = {}
            existing_drafts_created = 0
            existing_total_targets = None
            existing_failed_count = 0

            if has_progress_columns:
                result = await db.execute(select(Job).where(Job.id == job_uuid))
                job = result.scalar_one_or_none()

                if not job:
                    logger.error(f"❌ [DRAFTING] Job {job_id} not found")
                    return {"error": "Job not found"}

                job_params = job.params or {}
                existing_drafts_created = job.drafts_created or 0
                existing_total_targets = job.total_targets
                if isinstance(job.result, dict):
                    existing_failed_count = job.result.get("failed") or 0
                job.status = "running"
                await db.commit()
                await db.refresh(job)
            else:
                result = await db.execute(
                    text(
                        """
                        SELECT id, params, status, result, error_message
                        FROM jobs
                        WHERE id = :job_id
                        """
                    ),
                    {"job_id": str(job_uuid)},
                )
                row = result.fetchone()

                if not row:
                    logger.error(f"❌ [DRAFTING] Job {job_id} not found")
                    return {"error": "Job not found"}

                row_mapping = row._mapping
                job_params = _coerce_json_value(row_mapping.get("params"))
                result_data = _coerce_json_value(row_mapping.get("result"))
                if result_data:
                    existing_drafts_created = (
                        result_data.get("drafts_created")
                        or result_data.get("drafted")
                        or 0
                    )
                    existing_total_targets = (
                        result_data.get("total_targets")
                        or result_data.get("total")
                    )
                    existing_failed_count = result_data.get("failed") or 0
                await db.execute(
                    text(
                        "UPDATE jobs SET status = 'running', updated_at = NOW() WHERE id = :job_id"
                    ),
                    {"job_id": str(job_uuid)},
                )
                await db.commit()

            job_mode = job_params.get("mode") if isinstance(job_params, dict) else None
            prospect_ids = job_params.get("prospect_ids") if isinstance(job_params, dict) else None
            auto_mode = bool(job_params.get("auto_mode")) if isinstance(job_params, dict) else False
            if not prospect_ids and job_mode != "category":
                auto_mode = True

            category_filters = job_params.get("filters") if isinstance(job_params, dict) else None
            category_filter_value = None
            if isinstance(category_filters, dict):
                category_filter_value = category_filters.get("category")

            email_present_filter = and_(
                Prospect.contact_email.isnot(None),
                func.length(func.trim(Prospect.contact_email)) > 0,
            )
            draft_missing_filter = or_(
                Prospect.draft_subject.is_(None),
                func.length(func.trim(Prospect.draft_subject)) == 0,
                Prospect.draft_body.is_(None),
                func.length(func.trim(Prospect.draft_body)) == 0,
            )
            website_filter = or_(
                Prospect.source_type == "website",
                Prospect.source_type.is_(None),
            )
            scraped_filter = Prospect.scrape_status.in_([
                ScrapeStatus.SCRAPED.value,
                ScrapeStatus.ENRICHED.value,
            ])
            eligible_filter = and_(
                website_filter,
                scraped_filter,
                email_present_filter,
                draft_missing_filter,
            )

            if job_mode == "category" and not prospect_ids:
                if not category_filter_value:
                    error_message = "Category drafting job missing filters.category"
                    logger.error(f"❌ [DRAFTING] {error_message}")
                    if has_progress_columns and job:
                        job.status = "failed"
                        job.error_message = error_message
                        await db.commit()
                    else:
                        await db.execute(
                            text(
                                "UPDATE jobs SET status = 'failed', error_message = :error, updated_at = NOW() WHERE id = :job_id"
                            ),
                            {"job_id": str(job_uuid), "error": error_message},
                        )
                        await db.commit()
                    return {"error": error_message}

                result = await db.execute(
                    select(Prospect).where(
                        and_(
                            eligible_filter,
                            Prospect.discovery_category == category_filter_value,
                        )
                    )
                )
                prospects = result.scalars().all()
                logger.info(
                    f"📋 [DRAFTING] Found {len(prospects)} prospects for category '{category_filter_value}'"
                )
            elif auto_mode:
                result = await db.execute(select(Prospect).where(eligible_filter))
                prospects = result.scalars().all()
                logger.info(
                    f"📋 [DRAFTING] Found {len(prospects)} leads/scraped emails without drafts"
                )
            else:
                try:
                    prospect_uuid_list = [UUID(pid) for pid in (prospect_ids or [])]
                except Exception as e:
                    error_message = f"Invalid prospect_ids in job params: {e}"
                    logger.error(f"❌ [DRAFTING] {error_message}", exc_info=True)
                    if has_progress_columns and job:
                        job.status = "failed"
                        job.error_message = error_message
                        await db.commit()
                    else:
                        await db.execute(
                            text(
                                "UPDATE jobs SET status = 'failed', error_message = :error, updated_at = NOW() WHERE id = :job_id"
                            ),
                            {"job_id": str(job_uuid), "error": error_message},
                        )
                        await db.commit()
                    return {"error": error_message}

                result = await db.execute(
                    select(Prospect).where(
                        and_(
                            Prospect.id.in_(prospect_uuid_list),
                            eligible_filter,
                        )
                    )
                )
                prospects = result.scalars().all()

                if len(prospects) == 0:
                    error_message = (
                        "No valid prospects found. Ensure they appear in Leads/Scraped Emails, have emails, and no existing drafts."
                    )
                    logger.warning("⚠️  [DRAFTING] No valid prospects found for provided IDs")
                    if has_progress_columns and job:
                        job.status = "failed"
                        job.error_message = error_message
                        job.result = {
                            "drafted": 0,
                            "failed": 0,
                            "total": 0,
                            "drafts_created": 0,
                            "total_targets": 0,
                        }
                        await db.commit()
                    else:
                        await db.execute(
                            text(
                                "UPDATE jobs SET status = 'failed', error_message = :error, result = :result, updated_at = NOW() WHERE id = :job_id"
                            ),
                            {
                                "job_id": str(job_uuid),
                                "error": error_message,
                                "result": json.dumps(
                                    {
                                        "drafted": 0,
                                        "failed": 0,
                                        "total": 0,
                                        "drafts_created": 0,
                                        "total_targets": 0,
                                    }
                                ),
                            },
                        )
                        await db.commit()
                    return {"error": "No valid prospects found"}

            total_targets = len(prospects)
            if existing_total_targets:
                total_targets = max(existing_total_targets, total_targets)

            if total_targets == 0:
                error_message = "No eligible leads/scraped emails ready for drafting"
                if existing_total_targets and existing_drafts_created >= (existing_total_targets or 0):
                    status = "completed"
                    error_message = None
                elif existing_drafts_created > 0:
                    status = "completed"
                    error_message = None
                else:
                    status = "failed"
                logger.warning("⚠️  [DRAFTING] No eligible prospects ready for drafting")
                job_result = {
                    "drafted": existing_drafts_created,
                    "failed": existing_failed_count,
                    "total": total_targets,
                    "drafts_created": existing_drafts_created,
                    "total_targets": total_targets,
                }
                if has_progress_columns and job:
                    job.status = status
                    job.error_message = error_message
                    job.drafts_created = existing_drafts_created
                    job.total_targets = total_targets
                    job.result = job_result
                    await db.commit()
                else:
                    await db.execute(
                        text(
                            "UPDATE jobs SET status = :status, error_message = :error, result = :result, updated_at = NOW() WHERE id = :job_id"
                        ),
                        {
                            "job_id": str(job_uuid),
                            "status": status,
                            "error": error_message,
                            "result": json.dumps(job_result),
                        },
                    )
                    await db.commit()
                return {
                    "job_id": job_id,
                    "status": status,
                    "drafted": existing_drafts_created,
                    "failed": existing_failed_count,
                    "message": error_message,
                }

            if has_progress_columns and job:
                job.total_targets = total_targets
                job.drafts_created = existing_drafts_created
                job.result = {
                    "drafted": existing_drafts_created,
                    "failed": existing_failed_count,
                    "total": total_targets,
                    "drafts_created": existing_drafts_created,
                    "total_targets": total_targets,
                }
                await db.commit()
                await db.refresh(job)
            else:
                await db.execute(
                    text(
                        "UPDATE jobs SET result = :result, updated_at = NOW() WHERE id = :job_id"
                    ),
                    {
                        "job_id": str(job_uuid),
                        "result": json.dumps(
                            {
                                "drafted": existing_drafts_created,
                                "failed": existing_failed_count,
                                "total": total_targets,
                                "drafts_created": existing_drafts_created,
                                "total_targets": total_targets,
                            }
                        ),
                    },
                )
                await db.commit()

            logger.info(
                f"✍️  [DRAFTING] Starting drafting for {total_targets} prospects (job {job_id})"
            )

            try:
                gemini_client = GeminiClient()
            except Exception as e:
                error_message = f"Gemini not configured: {e}"
                logger.error(f"❌ [DRAFTING] Failed to initialize Gemini client: {e}")
                if has_progress_columns and job:
                    job.status = "failed"
                    job.error_message = error_message
                    await db.commit()
                else:
                    await db.execute(
                        text(
                            "UPDATE jobs SET status = 'failed', error_message = :error, updated_at = NOW() WHERE id = :job_id"
                        ),
                        {"job_id": str(job_uuid), "error": error_message},
                    )
                    await db.commit()
                return {"error": error_message}

            drafted_count = existing_drafts_created
            failed_count = existing_failed_count
            skipped_count = 0

            category_concept = None
            category_subject_template = None
            category_body_template = None
            if job_mode == "category" and isinstance(job_params, dict):
                category_concept = (job_params.get("concept") or "").strip() or None
                category_subject_template = (job_params.get("subject_template") or "").strip() or None
                category_body_template = (job_params.get("body_template") or "").strip() or None

            for idx, prospect in enumerate(prospects, 1):
                try:
                    if has_progress_columns and job:
                        await db.refresh(job)
                        if job.status == "cancelled":
                            logger.warning(
                                f"⚠️  [DRAFTING] Job {job_id} cancelled - stopping"
                            )
                            return {"job_id": job_id, "status": "cancelled"}
                    else:
                        status_result = await db.execute(
                            text("SELECT status FROM jobs WHERE id = :job_id"),
                            {"job_id": str(job_uuid)},
                        )
                        status_row = status_result.fetchone()
                        if status_row and status_row[0] == "cancelled":
                            logger.warning(
                                f"⚠️  [DRAFTING] Job {job_id} cancelled - stopping"
                            )
                            return {"job_id": job_id, "status": "cancelled"}

                    if _has_complete_draft(prospect):
                        skipped_count += 1
                        continue

                    logger.info(
                        f"✍️  [DRAFTING] [{idx}/{total_targets}] Drafting email for {prospect.domain}..."
                    )

                    page_snippet = None
                    if isinstance(prospect.dataforseo_payload, dict):
                        page_snippet = prospect.dataforseo_payload.get("description") or prospect.dataforseo_payload.get(
                            "snippet"
                        )

                    if job_mode == "category":
                        if not category_concept or not category_subject_template or not category_body_template:
                            raise ValueError("Category drafting missing concept/subject_template/body_template")

                        gemini_result = await gemini_client.compose_email_from_template(
                            domain=prospect.domain,
                            page_title=prospect.page_title,
                            page_url=prospect.page_url,
                            page_snippet=page_snippet,
                            category=prospect.discovery_category,
                            concept=category_concept,
                            subject_template=category_subject_template,
                            body_template=category_body_template,
                        )
                    else:
                        gemini_result = await gemini_client.compose_email(
                            domain=prospect.domain,
                            page_title=prospect.page_title,
                            page_url=prospect.page_url,
                            page_snippet=page_snippet,
                            contact_name=None,
                            category=prospect.discovery_category,
                        )

                    if gemini_result.get("success"):
                        subject = (gemini_result.get("subject") or "").strip()
                        body = (gemini_result.get("body") or "").strip()
                        if not subject or not body:
                            raise ValueError("Gemini returned empty subject/body")

                        update_result = await db.execute(
                            update(Prospect)
                            .where(
                                and_(
                                    Prospect.id == prospect.id,
                                    draft_missing_filter,
                                )
                            )
                            .values(
                                draft_subject=subject,
                                draft_body=body,
                                draft_status=DraftStatus.DRAFTED.value,
                                stage=ProspectStage.DRAFTED.value,
                                updated_at=func.now(),
                            )
                        )

                        if update_result.rowcount == 0:
                            skipped_count += 1
                        else:
                            drafted_count += 1
                            logger.info(
                                f"✅ [DRAFTING] [{drafted_count}/{total_targets}] Drafted email for {prospect.domain}: {subject}"
                            )
                    else:
                        error = gemini_result.get("error", "Unknown error")
                        logger.error(
                            f"❌ [DRAFTING] Gemini failed for {prospect.domain} ({prospect.contact_email}): {error}"
                        )
                        failed_count += 1
                        await db.execute(
                            update(Prospect)
                            .where(
                                and_(
                                    Prospect.id == prospect.id,
                                    draft_missing_filter,
                                )
                            )
                            .values(
                                draft_status=DraftStatus.FAILED.value,
                                updated_at=func.now(),
                            )
                        )

                    job_result = {
                        "drafted": drafted_count,
                        "failed": failed_count,
                        "total": total_targets,
                        "drafts_created": drafted_count,
                        "total_targets": total_targets,
                        "skipped": skipped_count,
                    }

                    if has_progress_columns and job:
                        job.drafts_created = drafted_count
                        job.result = job_result
                    else:
                        await db.execute(
                            text(
                                "UPDATE jobs SET result = :result, updated_at = NOW() WHERE id = :job_id"
                            ),
                            {"job_id": str(job_uuid), "result": json.dumps(job_result)},
                        )

                    await db.commit()
                    await asyncio.sleep(1)

                except Exception as e:
                    logger.error(
                        f"❌ [DRAFTING] Failed to draft {prospect.domain} ({prospect.contact_email}): {e}",
                        exc_info=True,
                    )
                    failed_count += 1
                    await db.execute(
                        update(Prospect)
                        .where(
                            and_(
                                Prospect.id == prospect.id,
                                draft_missing_filter,
                            )
                        )
                        .values(
                            draft_status=DraftStatus.FAILED.value,
                            updated_at=func.now(),
                        )
                    )
                    job_result = {
                        "drafted": drafted_count,
                        "failed": failed_count,
                        "total": total_targets,
                        "drafts_created": drafted_count,
                        "total_targets": total_targets,
                        "skipped": skipped_count,
                    }
                    if has_progress_columns and job:
                        job.drafts_created = drafted_count
                        job.result = job_result
                    else:
                        await db.execute(
                            text(
                                "UPDATE jobs SET result = :result, updated_at = NOW() WHERE id = :job_id"
                            ),
                            {"job_id": str(job_uuid), "result": json.dumps(job_result)},
                        )
                    await db.commit()
                    continue

            final_result = {
                "drafted": drafted_count,
                "failed": failed_count,
                "total": total_targets,
                "drafts_created": drafted_count,
                "total_targets": total_targets,
                "skipped": skipped_count,
            }

            if drafted_count == 0:
                status = "failed"
                error_message = (
                    "No drafts created. Check Gemini configuration and prospect eligibility."
                    if failed_count > 0
                    else "No eligible leads/scraped emails were available to draft."
                )
            else:
                status = "completed"
                error_message = (
                    f"{failed_count} drafts failed during processing."
                    if failed_count > 0
                    else None
                )

            if has_progress_columns and job:
                job.status = status
                job.error_message = error_message
                job.drafts_created = drafted_count
                job.result = final_result
                await db.commit()
            else:
                await db.execute(
                    text(
                        "UPDATE jobs SET status = :status, error_message = :error, result = :result, updated_at = NOW() WHERE id = :job_id"
                    ),
                    {
                        "job_id": str(job_uuid),
                        "status": status,
                        "error": error_message,
                        "result": json.dumps(final_result),
                    },
                )
                await db.commit()

            logger.info(
                f"✅ [DRAFTING] Job {job_id} completed: {drafted_count} drafted, {failed_count} failed"
            )

            return {
                "job_id": job_id,
                "status": status,
                "drafted": drafted_count,
                "failed": failed_count,
            }
            
        except Exception as e:
            logger.error(f"❌ [DRAFTING] Job {job_id} failed: {e}", exc_info=True)
            try:
                job_uuid = UUID(job_id)
                if await _job_progress_columns_exist(db):
                    result = await db.execute(select(Job).where(Job.id == job_uuid))
                    job = result.scalar_one_or_none()
                    if job:
                        job.status = "failed"
                        job.error_message = str(e)
                        await db.commit()
                else:
                    await db.execute(
                        text(
                            "UPDATE jobs SET status = 'failed', error_message = :error, updated_at = NOW() WHERE id = :job_id"
                        ),
                        {"job_id": str(job_uuid), "error": str(e)},
                    )
                    await db.commit()
            except Exception as commit_err:
                logger.error(f"❌ [DRAFTING] Failed to commit error status: {commit_err}", exc_info=True)
            return {"error": str(e)}
        finally:
            try:
                from app.task_manager import unregister_task

                unregister_task(str(job_id))
            except Exception:
                pass

