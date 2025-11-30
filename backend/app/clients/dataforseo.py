"""
DataForSEO API client for website discovery and on-page crawling
Fully validated and diagnostic-enabled implementation
"""
import httpx
import base64
import asyncio
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
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
        
        # Normalize
        self.keyword = str(self.keyword).strip()
        self.language_code = str(self.language_code).strip().lower()
        self.location_code = int(self.location_code)
        self.depth = int(self.depth)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "keyword": self.keyword,
            "location_code": self.location_code,
            "language_code": self.language_code,
            "depth": self.depth
        }


class DataForSEOClient:
    """Client for DataForSEO API with full validation and diagnostics"""
    
    BASE_URL = "https://api.dataforseo.com/v3"
    
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
            location: Location name (usa, canada, uk_london, germany, france, europe)
        
        Returns:
            Location code for DataForSEO API
        """
        location_map = {
            "usa": 2840,
            "canada": 2124,
            "uk_london": 2826,
            "germany": 2276,
            "france": 2250,
            "europe": 2036,
        }
        return location_map.get(location.lower(), 2840)  # Default to USA
    
    def _build_payload(self, payload_obj: DataForSEOPayload) -> list:
        """
        Build DataForSEO API payload according to v3 specification
        
        CRITICAL: DataForSEO v3 expects a DIRECT JSON array, NOT wrapped in "data" key!
        According to official docs: payload must be a JSON array of task objects.
        
        Required fields: keyword, location_code, language_code
        Optional fields: depth (defaults to 10 if not specified)
        CRITICAL: Do NOT include device, os, or other fields that cause 40503 error
        
        Returns:
            List of task objects (direct array format, NOT wrapped in "data")
        """
        return [payload_obj.to_dict()]
    
    def _validate_response(self, response: httpx.Response, result: dict) -> tuple[bool, Optional[str]]:
        """
        Validate DataForSEO API response
        
        Returns:
            (is_valid, error_message)
        """
        # Check HTTP status
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}: {response.text[:200]}"
        
        # Check top-level status
        status_code = result.get("status_code")
        if status_code != 20000:
            status_msg = result.get("status_message", "Unknown error")
            return False, f"API error {status_code}: {status_msg}"
        
        # Check tasks array
        tasks = result.get("tasks", [])
        if not tasks:
            return False, "No tasks in response"
        
        # Check first task status
        task = tasks[0]
        task_status = task.get("status_code")
        if task_status != 20000:
            task_msg = task.get("status_message", "Unknown task error")
            return False, f"Task error {task_status}: {task_msg}"
        
        return True, None
    
    async def serp_google_organic(
        self,
        keyword: str,
        location_code: int = 2840,
        language_code: str = "en",
        depth: int = 10
    ) -> Dict[str, Any]:
        """
        Search Google SERP using DataForSEO API
        
        Args:
            keyword: Search keyword
            location_code: Location code (default: 2840 for USA)
            language_code: Language code (default: "en")
            depth: Number of results to fetch (default: 10)
        
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
                depth=depth
            )
            
            payload = self._build_payload(payload_obj)
            
            # Log exact payload being sent
            payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
            logger.info(f"DataForSEO Request #{self._request_count}")
            logger.info(f"Payload (exact):\n{payload_json}")
            
            url = f"{self.BASE_URL}/serp/google/organic/task_post"
            
            # Store request for diagnostics
            self._last_request = {
                "url": url,
                "payload": payload,
                "timestamp": datetime.utcnow().isoformat(),
                "keyword": keyword,
                "location_code": location_code
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                # CRITICAL: DataForSEO requires exact JSON format
                # Use httpx's json parameter - it handles serialization correctly
                # and sets Content-Type automatically
                logger.debug(f"Payload dict: {payload}")
                logger.debug(f"Payload JSON: {json.dumps(payload, indent=2)}")
                
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
                    logger.error(error_msg)
                    logger.error(f"Response text: {response.text[:500]}")
                    self._error_count += 1
                    self._last_error = error_msg
                    return {"success": False, "error": error_msg}
                
                # Store response for diagnostics
                self._last_response = {
                    "status_code": response.status_code,
                    "result": result,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Validate response
                is_valid, error_msg = self._validate_response(response, result)
                
                if not is_valid:
                    logger.error(f"DataForSEO validation failed: {error_msg}")
                    logger.error(f"Full response: {json.dumps(result, indent=2)}")
                    self._error_count += 1
                    self._last_error = error_msg
                    return {"success": False, "error": error_msg}
                
                # Extract task ID
                task = result.get("tasks", [])[0]
                task_id = task.get("id")
                
                if not task_id:
                    error_msg = "No task ID in response"
                    logger.error(error_msg)
                    logger.error(f"Task object: {json.dumps(task, indent=2)}")
                    self._error_count += 1
                    self._last_error = error_msg
                    return {"success": False, "error": error_msg}
                
                logger.info(f"✅ DataForSEO task created: {task_id}")
                self._success_count += 1
                
                # Poll for results
                return await self._get_serp_results(task_id)
        
        except ValueError as e:
            # Validation error
            error_msg = f"Payload validation error: {str(e)}"
            logger.error(error_msg)
            self._error_count += 1
            self._last_error = error_msg
            return {"success": False, "error": error_msg}
        
        except Exception as e:
            error_msg = f"DataForSEO API call failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
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
        
        logger.info(f"Polling DataForSEO task: {task_id}")
        
        # Wait before first poll
        await asyncio.sleep(5)
        
        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    logger.debug(f"Poll attempt {attempt + 1}/{max_attempts} for task {task_id}")
                    response = await client.get(url, headers=self.headers)
                    response.raise_for_status()
                    result = response.json()
                    
                    if result.get("status_code") == 20000:
                        tasks = result.get("tasks", [])
                        if not tasks:
                            await asyncio.sleep(2)
                            continue
                        
                        task = tasks[0]
                        task_status = task.get("status_code")
                        
                        if task_status == 20000:
                            # Results ready
                            task_result = task.get("result", [])
                            if not task_result:
                                return {"success": False, "error": "No result data in task"}
                            
                            items = task_result[0].get("items", [])
                            
                            parsed_results = []
                            for item in items:
                                if item.get("type") == "organic":
                                    parsed_results.append({
                                        "title": item.get("title", ""),
                                        "url": item.get("url", ""),
                                        "description": item.get("description", ""),
                                        "position": item.get("rank_group", 0),
                                        "domain": item.get("domain", ""),
                                    })
                            
                            logger.info(f"✅ Retrieved {len(parsed_results)} organic results")
                            return {
                                "success": True,
                                "results": parsed_results,
                                "total": len(parsed_results)
                            }
                        elif task_status == 20200:
                            # Still processing
                            await asyncio.sleep(3)
                            continue
                        else:
                            error_msg = task.get("status_message", f"Status {task_status}")
                            return {"success": False, "error": error_msg}
                    else:
                        error_msg = result.get("status_message", f"API error: {result.get('status_code')}")
                        return {"success": False, "error": error_msg}
            
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    # Task not found - wait longer
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(5)
                        continue
                    return {"success": False, "error": f"Task not found after {max_attempts} attempts"}
                else:
                    error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                    if attempt == max_attempts - 1:
                        return {"success": False, "error": error_msg}
                    await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Error polling task {task_id}: {str(e)}", exc_info=True)
                if attempt == max_attempts - 1:
                    return {"success": False, "error": str(e)}
                await asyncio.sleep(3)
        
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
            "credentials_configured": bool(self.login and self.password)
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
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                logger.info(f"Submitting DataForSEO on-page task for domain: {domain}")
                response = await client.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                result = response.json()
                
                if result.get("status_code") == 20000:
                    task_id = result.get("tasks", [{}])[0].get("id")
                    return {"success": True, "task_id": task_id}
                else:
                    error_msg = result.get("status_message", "Unknown error")
                    return {"success": False, "error": error_msg}
        
        except Exception as e:
            logger.error(f"DataForSEO on-page task submission failed: {str(e)}")
            return {"success": False, "error": str(e)}
