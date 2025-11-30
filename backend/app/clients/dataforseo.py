"""
DataForSEO API client for website discovery and on-page crawling
Fully validated, diagnostic-enabled, and debugged implementation
"""
import httpx
import base64
import asyncio
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import os
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class DataForSEOPayload:
    """Validated DataForSEO task payload structure"""
    keyword: str
    location_code: int
    language_code: str = "en"
    depth: int = 10
    device: str = "desktop"  # Added per user requirement
    
    def __post_init__(self):
        """Validate payload fields"""
        if not self.keyword or not self.keyword.strip():
            raise ValueError("keyword cannot be empty")
        if self.location_code <= 0:
            raise ValueError(f"location_code must be positive, got {self.location_code}")
        if not self.language_code or len(self.language_code) != 2:
            raise ValueError(f"language_code must be 2 characters, got '{self.language_code}'")
        if self.depth < 1 or self.depth > 100:
            raise ValueError(f"depth must be between 1 and 100, got {self.depth}")
        if self.device not in ["desktop", "mobile", "tablet"]:
            raise ValueError(f"device must be 'desktop', 'mobile', or 'tablet', got '{self.device}'")
        
        # Normalize
        self.keyword = str(self.keyword).strip()
        self.language_code = str(self.language_code).strip().lower()
        self.location_code = int(self.location_code)
        self.depth = int(self.depth)
        self.device = str(self.device).strip().lower()
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "keyword": self.keyword,
            "location_code": self.location_code,
            "language_code": self.language_code,
            "depth": self.depth,
            "device": self.device
        }


class DataForSEOClient:
    """Client for DataForSEO API with full validation and diagnostics"""
    
    BASE_URL = "https://api.dataforseo.com/v3"
    
    # Official DataForSEO location code mapping
    LOCATION_MAP = {
        "usa": 2840,
        "united states": 2840,
        "us": 2840,
        "canada": 2124,
        "uk_london": 2826,
        "uk": 2826,
        "united kingdom": 2826,
        "london": 2826,
        "germany": 2276,
        "deutschland": 2276,
        "france": 2250,
        "europe": 2036,
    }
    
    def __init__(self, login: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize DataForSEO client
        
        Args:
            login: DataForSEO login/email (if None, uses DATAFORSEO_LOGIN from env)
            password: DataForSEO password/token (if None, uses DATAFORSEO_PASSWORD from env)
        """
        self.login = login or os.getenv("DATAFORSEO_LOGIN")
        self.password = password or os.getenv("DATAFORSEO_PASSWORD")
        
        if not self.login or not self.password:
            raise ValueError("DataForSEO credentials not configured. Set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD")
        
        # Validate credentials format
        if not self.login.strip() or not self.password.strip():
            raise ValueError("DataForSEO credentials cannot be empty")
        
        # Create basic auth header
        credentials = f"{self.login}:{self.password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {encoded_credentials}"
        }
        
        # Diagnostics tracking
        self._request_count = 0
        self._success_count = 0
        self._error_count = 0
        self._last_request = None
        self._last_response = None
        self._last_error = None
    
    def get_location_code(self, location: str) -> int:
        """
        Get location code for DataForSEO API
        
        Args:
            location: Location name (usa, canada, uk_london, germany, france, europe, etc.)
        
        Returns:
            Location code for DataForSEO API
        """
        location_lower = location.lower().strip()
        code = self.LOCATION_MAP.get(location_lower)
        
        if code is None:
            logger.warning(f"Unknown location '{location}', defaulting to USA (2840)")
            return 2840  # Default to USA
        
        logger.debug(f"Location '{location}' mapped to code {code}")
        return code
    
    def _build_payload(self, payload_obj: DataForSEOPayload) -> list:
        """
        Build DataForSEO API payload according to v3 specification
        
        CRITICAL: DataForSEO v3 expects a DIRECT JSON array, NOT wrapped in "data" key!
        Format: [{"keyword": "...", "location_code": 2840, "language_code": "en", "depth": 10, "device": "desktop"}]
        
        Returns:
            List of task objects (direct array format)
        """
        return [payload_obj.to_dict()]
    
    def _validate_task_post_response(self, response: httpx.Response, result: dict) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate DataForSEO task_post API response
        
        Returns:
            (is_valid, error_message, task_id)
        """
        # Check HTTP status
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}: {response.text[:200]}", None
        
        # Check top-level status
        status_code = result.get("status_code")
        if status_code != 20000:
            status_msg = result.get("status_message", "Unknown error")
            return False, f"API error {status_code}: {status_msg}", None
        
        # Check tasks array (defensive check)
        tasks = result.get("tasks")
        if not tasks:
            return False, "No tasks in response", None
        
        if not isinstance(tasks, list) or len(tasks) == 0:
            return False, f"Invalid tasks structure: expected list, got {type(tasks).__name__}", None
        
        # Check first task status
        task = tasks[0]
        if not isinstance(task, dict):
            return False, f"Invalid task structure: expected dict, got {type(task).__name__}", None
        
        task_status = task.get("status_code")
        task_id = task.get("id")
        
        # CRITICAL FIX: 20100 means "Task Created" - this is SUCCESS, not an error!
        # 20000 = Task completed with results
        # 20100 = Task created successfully (needs polling)
        # 20200 = Task still processing
        if task_status == 20000:
            # Task completed immediately (unlikely for SERP, but possible)
            logger.info(f"Task {task_id} completed immediately (20000)")
            return True, None, task_id
        elif task_status == 20100:
            # Task created successfully - this is GOOD, we need to poll
            logger.info(f"Task {task_id} created successfully (20100) - will poll for results")
            return True, None, task_id
        elif task_status == 20200:
            # Task still processing - also valid, continue polling
            logger.info(f"Task {task_id} still processing (20200) - will poll for results")
            return True, None, task_id
        else:
            # Actual error
            task_msg = task.get("status_message", "Unknown task error")
            return False, f"Task error {task_status}: {task_msg}", task_id
    
    async def serp_google_organic(
        self,
        keyword: str,
        location_code: int = 2840,
        language_code: str = "en",
        depth: int = 10,
        device: str = "desktop"
    ) -> Dict[str, Any]:
        """
        Search Google SERP using DataForSEO API
        
        Args:
            keyword: Search keyword
            location_code: Location code (default: 2840 for USA)
            language_code: Language code (default: "en")
            depth: Number of results to fetch (default: 10)
            device: Device type - "desktop", "mobile", or "tablet" (default: "desktop")
        
        Returns:
            Dictionary with search results
        """
        self._request_count += 1
        
        try:
            # Validate and build payload
            payload_obj = DataForSEOPayload(
                keyword=keyword,
                location_code=location_code,
                language_code=language_code,
                depth=depth,
                device=device
            )
            
            payload = self._build_payload(payload_obj)
            
            # Log exact payload being sent
            payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
            logger.info(f"🔵 DataForSEO Request #{self._request_count}")
            logger.info(f"🔵 Endpoint: {self.BASE_URL}/serp/google/organic/task_post")
            logger.info(f"🔵 Payload (exact JSON):\n{payload_json}")
            logger.info(f"🔵 Keyword: '{keyword}', Location: {location_code}, Language: '{language_code}', Device: '{device}'")
            
            url = f"{self.BASE_URL}/serp/google/organic/task_post"
            
            # Store request for diagnostics
            self._last_request = {
                "url": url,
                "payload": payload,
                "payload_json": payload_json,
                "timestamp": datetime.utcnow().isoformat(),
                "keyword": keyword,
                "location_code": location_code,
                "language_code": language_code,
                "device": device
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Send using json parameter (httpx handles encoding and Content-Type)
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload  # httpx will serialize this correctly
                )
                
                # Parse response
                try:
                    result = response.json()
                except Exception as e:
                    error_msg = f"Failed to parse JSON response: {e}"
                    logger.error(f"🔴 {error_msg}")
                    logger.error(f"🔴 Response text: {response.text[:500]}")
                    self._error_count += 1
                    self._last_error = error_msg
                    return {"success": False, "error": error_msg}
                
                # Log full response
                response_json = json.dumps(result, ensure_ascii=False, indent=2)
                logger.info(f"🔵 DataForSEO Response (full):\n{response_json}")
                
                # Store response for diagnostics
                self._last_response = {
                    "status_code": response.status_code,
                    "result": result,
                    "result_json": response_json,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Validate response
                is_valid, error_msg, task_id = self._validate_task_post_response(response, result)
                
                if not is_valid:
                    logger.error(f"🔴 DataForSEO validation failed: {error_msg}")
                    logger.error(f"🔴 Full response: {response_json}")
                    self._error_count += 1
                    self._last_error = error_msg
                    return {"success": False, "error": error_msg}
                
                if not task_id:
                    error_msg = "No task ID in response"
                    logger.error(f"🔴 {error_msg}")
                    logger.error(f"🔴 Task object: {json.dumps(result.get('tasks', [{}])[0] if result.get('tasks') else {}, indent=2)}")
                    self._error_count += 1
                    self._last_error = error_msg
                    return {"success": False, "error": error_msg}
                
                logger.info(f"✅ DataForSEO task created successfully: {task_id}")
                self._success_count += 1
                
                # Poll for results
                return await self._get_serp_results(task_id)
        
        except ValueError as e:
            # Validation error
            error_msg = f"Payload validation error: {str(e)}"
            logger.error(f"🔴 {error_msg}")
            self._error_count += 1
            self._last_error = error_msg
            return {"success": False, "error": error_msg}
        
        except Exception as e:
            error_msg = f"DataForSEO API call failed: {str(e)}"
            logger.error(f"🔴 {error_msg}", exc_info=True)
            self._error_count += 1
            self._last_error = error_msg
            return {"success": False, "error": error_msg}
    
    async def _get_serp_results(self, task_id: str, max_attempts: int = 30) -> Dict[str, Any]:
        """
        Poll DataForSEO API for SERP results
        
        Args:
            task_id: Task ID from task_post
            max_attempts: Maximum polling attempts (default: 30)
        
        Returns:
            Dictionary with parsed results
        """
        url = f"{self.BASE_URL}/serp/google/organic/task_get/advanced/{task_id}"
        
        logger.info(f"🔄 Polling DataForSEO task: {task_id}")
        logger.info(f"🔄 Poll URL: {url}")
        
        # Wait before first poll (task needs time to process)
        await asyncio.sleep(5)
        
        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    logger.debug(f"🔄 Poll attempt {attempt + 1}/{max_attempts} for task {task_id}")
                    response = await client.get(url, headers=self.headers)
                    response.raise_for_status()
                    result = response.json()
                    
                    # Log poll response
                    logger.debug(f"🔄 Poll response status_code: {result.get('status_code')}")
                    
                    if result.get("status_code") == 20000:
                        tasks = result.get("tasks")
                        if not tasks:
                            logger.warning(f"⚠️  No tasks in poll response for task_id {task_id}")
                            await asyncio.sleep(2)
                            continue
                        
                        if not isinstance(tasks, list) or len(tasks) == 0:
                            logger.warning(f"⚠️  Invalid tasks structure for task_id {task_id}: {type(tasks)}")
                            await asyncio.sleep(2)
                            continue
                        
                        task = tasks[0]
                        if not isinstance(task, dict):
                            logger.warning(f"⚠️  Invalid task structure (not a dict) for task_id {task_id}: {type(task)}")
                            await asyncio.sleep(2)
                            continue
                        
                        task_status = task.get("status_code")
                        task_msg = task.get("status_message", "")
                        
                        logger.info(f"🔄 Task {task_id} status: {task_status} - {task_msg}")
                        
                        if task_status == 20000:
                            # Results ready
                            task_result = task.get("result")
                            
                            # Defensive check: ensure task_result is a non-empty list
                            if not task_result:
                                logger.warning(f"⚠️  No result data in task {task_id}")
                                return {"success": False, "error": "No result data in task"}
                            
                            if not isinstance(task_result, list):
                                logger.warning(f"⚠️  task_result is not a list for task {task_id}: {type(task_result)}")
                                return {"success": False, "error": f"Invalid task result structure: expected list, got {type(task_result).__name__}"}
                            
                            if len(task_result) == 0:
                                logger.warning(f"⚠️  task_result is empty list for task {task_id}")
                                return {"success": False, "error": "Task result is empty"}
                            
                            # Safely get items from first result
                            first_result = task_result[0]
                            if not first_result or not isinstance(first_result, dict):
                                logger.warning(f"⚠️  Invalid first_result structure for task {task_id}: {type(first_result)}")
                                return {"success": False, "error": f"Invalid first result structure: expected dict, got {type(first_result).__name__}"}
                            
                            items = first_result.get("items", [])
                            if not isinstance(items, list):
                                logger.warning(f"⚠️  items is not a list for task {task_id}: {type(items)}")
                                items = []
                            
                            parsed_results = []
                            for item in items:
                                # Defensive check: ensure item is a dict
                                if not isinstance(item, dict):
                                    logger.warning(f"⚠️  Skipping invalid item (not a dict): {type(item)}")
                                    continue
                                
                                if item.get("type") == "organic":
                                    # Safely handle None values from API
                                    parsed_results.append({
                                        "title": item.get("title") or "",
                                        "url": item.get("url") or "",
                                        "description": item.get("description") or "",
                                        "position": item.get("rank_group", 0) or 0,
                                        "domain": item.get("domain") or "",
                                    })
                            
                            logger.info(f"✅ Retrieved {len(parsed_results)} organic results from task {task_id}")
                            return {
                                "success": True,
                                "results": parsed_results,
                                "total": len(parsed_results),
                                "task_id": task_id
                            }
                        elif task_status == 20100:
                            # Task created but not ready yet - continue polling
                            logger.info(f"🔄 Task {task_id} created (20100) - waiting for processing...")
                            # Exponential backoff: 3s * (attempt + 1)
                            await asyncio.sleep(min(3 * (attempt + 1), 30))
                            continue
                        elif task_status == 20200:
                            # Still processing
                            logger.info(f"🔄 Task {task_id} still processing (20200) - waiting...")
                            # Exponential backoff: 3s * (attempt + 1)
                            await asyncio.sleep(min(3 * (attempt + 1), 30))
                            continue
                        elif task_status == 40602:
                            # Task in queue - continue polling (this is not an error)
                            logger.info(f"🔄 Task {task_id} in queue (40602) - waiting...")
                            # Exponential backoff: 3s * (attempt + 1)
                            await asyncio.sleep(min(3 * (attempt + 1), 30))
                            continue
                        elif task_status == 40601:
                            # Task Handed - task was handed to another processor, continue polling
                            logger.info(f"🔄 Task {task_id} handed to processor (40601) - waiting for completion...")
                            # Exponential backoff: 3s * (attempt + 1)
                            await asyncio.sleep(min(3 * (attempt + 1), 30))
                            continue
                        else:
                            # Error status
                            error_msg = task.get("status_message", f"Status {task_status}")
                            logger.error(f"🔴 Task {task_id} failed with status {task_status}: {error_msg}")
                            logger.error(f"🔴 Full task response: {json.dumps(task, indent=2)}")
                            return {"success": False, "error": f"Task status {task_status}: {error_msg}"}
                    else:
                        error_msg = result.get("status_message", f"API error: {result.get('status_code')}")
                        logger.error(f"🔴 DataForSEO API error: {error_msg}")
                        logger.error(f"🔴 Full API response: {json.dumps(result, indent=2)}")
                        return {"success": False, "error": error_msg}
            
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    # Task not found - wait longer
                    logger.warning(f"⚠️  Task {task_id} not found (404) - attempt {attempt + 1}/{max_attempts}")
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(5)
                        continue
                    return {"success": False, "error": f"Task not found after {max_attempts} attempts"}
                else:
                    error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                    logger.error(f"🔴 HTTP error polling task {task_id}: {error_msg}")
                    if attempt == max_attempts - 1:
                        return {"success": False, "error": error_msg}
                    await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"🔴 Error polling task {task_id}: {str(e)}", exc_info=True)
                if attempt == max_attempts - 1:
                    return {"success": False, "error": str(e)}
                await asyncio.sleep(3)
        
        logger.error(f"🔴 Timeout waiting for task {task_id} results after {max_attempts} attempts")
        return {"success": False, "error": "Timeout waiting for results"}
    
    def get_diagnostics(self) -> Dict[str, Any]:
        """
        Get diagnostic information about API usage
        
        Returns:
            Dictionary with diagnostic data
        """
        return {
            "request_count": self._request_count,
            "success_count": self._success_count,
            "error_count": self._error_count,
            "success_rate": (self._success_count / self._request_count * 100) if self._request_count > 0 else 0,
            "last_request": self._last_request,
            "last_response": self._last_response,
            "last_error": self._last_error,
            "credentials_configured": bool(self.login and self.password),
            "location_map": self.LOCATION_MAP
        }
    
    async def on_page_task_post(self, domain: str, max_crawl_pages: int = 5) -> Dict[str, Any]:
        """
        Submit on-page crawling task to DataForSEO
        
        Args:
            domain: Domain to crawl
            max_crawl_pages: Maximum pages to crawl (default: 5)
        
        Returns:
            Dictionary with task ID
        """
        url = f"{self.BASE_URL}/on_page/task_post"
        
        # CRITICAL: DataForSEO expects direct JSON array, NOT wrapped in "data"
        payload = [{
            "target": domain,
            "max_crawl_pages": max_crawl_pages,
            "enable_javascript": True,
            "load_resources": True,
            "fetch_html": True,
            "respect_robot_txt": False,
            "custom_headers": {"User-Agent": "Mozilla/5.0"}
        }]
        
        logger.info(f"🔵 Submitting DataForSEO on-page task for domain: {domain}")
        logger.info(f"🔵 Payload: {json.dumps(payload, indent=2)}")
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                result = response.json()
                
                logger.info(f"🔵 On-page task response: {json.dumps(result, indent=2)}")
                
                if result.get("status_code") == 20000:
                    tasks = result.get("tasks", [])
                    if tasks and isinstance(tasks, list) and len(tasks) > 0:
                        task_id = tasks[0].get("id") if isinstance(tasks[0], dict) else None
                    else:
                        task_id = None
                    return {"success": True, "task_id": task_id}
                else:
                    error_msg = result.get("status_message", "Unknown error")
                    logger.error(f"🔴 On-page task failed: {error_msg}")
                    return {"success": False, "error": error_msg}
        
        except Exception as e:
            logger.error(f"🔴 DataForSEO on-page task submission failed: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}
