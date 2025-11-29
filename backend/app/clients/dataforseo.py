"""
DataForSEO API client for website discovery and on-page crawling
"""
import httpx
import base64
import asyncio
from typing import Dict, List, Optional, Any
import os
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)


class DataForSEOClient:
    """Client for DataForSEO API"""
    
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
        
        # Create basic auth header
        credentials = f"{self.login}:{self.password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {encoded_credentials}"
        }
    
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
        url = f"{self.BASE_URL}/serp/google/organic/task_post"
        
        payload = {
            "data": [{
                "keyword": keyword,
                "location_code": location_code,
                "language_code": language_code,
                "depth": depth,
                "device": "desktop",
                "os": "windows"
            }]
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                logger.info(f"Making DataForSEO SERP API call for keyword: '{keyword}'")
                logger.debug(f"DataForSEO task_post URL: {url}")
                logger.debug(f"DataForSEO task_post payload: {payload}")
                response = await client.post(url, headers=self.headers, json=payload)
                
                # Always parse JSON first, even on HTTP errors
                try:
                    result = response.json()
                except:
                    result = {"status_code": response.status_code, "status_message": response.text}
                
                logger.debug(f"DataForSEO task_post response: status_code={result.get('status_code')}, tasks_count={result.get('tasks_count', 0)}")
                logger.debug(f"Full response: {result}")
                
                # Check for HTTP errors
                if response.status_code != 200:
                    error_msg = result.get("status_message", f"HTTP {response.status_code}: {response.text}")
                    logger.error(f"DataForSEO task_post HTTP error: {error_msg}")
                    return {"success": False, "error": error_msg}
                
                if result.get("status_code") == 20000:
                    tasks = result.get("tasks", [])
                    if not tasks or len(tasks) == 0:
                        logger.error("No tasks in DataForSEO task_post response")
                        return {"success": False, "error": "No tasks returned from DataForSEO"}
                    
                    task = tasks[0]
                    task_status = task.get("status_code")
                    
                    # Check if task was created successfully
                    if task_status != 20000:
                        error_msg = task.get("status_message", f"Task creation failed with status {task_status}")
                        logger.error(f"DataForSEO task_post failed: {error_msg}")
                        return {"success": False, "error": error_msg}
                    
                    task_id = task.get("id")
                    if not task_id:
                        logger.error("No task ID in DataForSEO task response")
                        logger.error(f"Task response: {task}")
                        return {"success": False, "error": "No task ID returned from DataForSEO"}
                    
                    logger.info(f"✅ DataForSEO task created successfully: {task_id}")
                    
                    # Poll for results
                    return await self._get_serp_results(task_id)
                else:
                    error_msg = result.get("status_message", f"API error: {result.get('status_code')}")
                    logger.error(f"DataForSEO API error: {error_msg}")
                    logger.error(f"Full response: {result}")
                    return {"success": False, "error": error_msg}
        
        except Exception as e:
            logger.error(f"DataForSEO API call failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _get_serp_results(self, task_id: str, max_attempts: int = 30) -> Dict[str, Any]:
        """
        Poll DataForSEO API for SERP results
        
        Args:
            task_id: Task ID from task_post
            max_attempts: Maximum polling attempts (default: 30)
        
        Returns:
            Dictionary with parsed results
        """
        # DataForSEO task_get endpoint - use GET with task ID in URL path
        # Based on worker implementation and API docs, this is the correct format
        url = f"{self.BASE_URL}/serp/google/organic/task_get/advanced/{task_id}"
        
        logger.info(f"Polling DataForSEO task: {task_id}")
        logger.debug(f"Polling URL: {url}")
        
        # Wait a bit before first poll (task needs time to be created)
        await asyncio.sleep(5)  # Increased wait time
        
        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    logger.debug(f"Polling DataForSEO task {task_id} (attempt {attempt + 1}/{max_attempts})")
                    # DataForSEO task_get uses GET request with task ID in URL path
                    response = await client.get(url, headers=self.headers)
                    response.raise_for_status()
                    result = response.json()
                    
                    logger.debug(f"DataForSEO poll response status_code: {result.get('status_code')}")
                    
                    if result.get("status_code") == 20000:
                        tasks = result.get("tasks", [])
                        if not tasks:
                            logger.warning(f"No tasks in response for task_id {task_id}")
                            await asyncio.sleep(2)
                            continue
                        
                        task = tasks[0]
                        task_status = task.get("status_code")
                        
                        if task_status == 20000:
                            # Results are ready
                            task_result = task.get("result", [])
                            if not task_result:
                                logger.warning(f"No result data in task {task_id}")
                                return {"success": False, "error": "No result data in task"}
                            
                            items = task_result[0].get("items", [])
                            
                            parsed_results = []
                            for item in items:
                                # Only include organic results
                                if item.get("type") == "organic":
                                    parsed_results.append({
                                        "title": item.get("title", ""),
                                        "url": item.get("url", ""),
                                        "description": item.get("description", ""),
                                        "position": item.get("rank_group", 0),
                                        "domain": item.get("domain", ""),
                                    })
                            
                            logger.info(f"DataForSEO returned {len(parsed_results)} organic results")
                            return {
                                "success": True,
                                "results": parsed_results,
                                "total": len(parsed_results)
                            }
                        elif task_status == 20200:
                            # Still processing, wait and retry
                            logger.debug(f"Task {task_id} still processing (20200), waiting...")
                            await asyncio.sleep(3)
                            continue
                        else:
                            error_msg = task.get("status_message", f"Unknown status code: {task_status}")
                            logger.error(f"Task {task_id} failed with status {task_status}: {error_msg}")
                            return {"success": False, "error": error_msg}
                    else:
                        error_msg = result.get("status_message", f"API error: {result.get('status_code')}")
                        logger.error(f"DataForSEO API error: {error_msg}")
                        return {"success": False, "error": error_msg}
            
            except httpx.HTTPStatusError as e:
                error_text = e.response.text if e.response else "No response text"
                try:
                    error_json = e.response.json() if e.response else {}
                    error_status = error_json.get("status_code")
                    error_msg = error_json.get("status_message", error_text)
                    
                    # 40400 means task not found - might need to wait longer or task was never created
                    if error_status == 40400:
                        logger.warning(f"Task {task_id} not found (40400) - attempt {attempt + 1}/{max_attempts}. Waiting longer...")
                        if attempt < max_attempts - 1:
                            await asyncio.sleep(5)  # Wait longer for 404 errors
                            continue
                        else:
                            return {"success": False, "error": f"Task not found after {max_attempts} attempts. Task may not have been created or expired."}
                    else:
                        logger.error(f"HTTP error polling DataForSEO task {task_id}: {e.response.status_code} - {error_msg}")
                        if attempt == max_attempts - 1:
                            return {"success": False, "error": f"HTTP {e.response.status_code}: {error_msg}"}
                        await asyncio.sleep(3)
                except:
                    logger.error(f"HTTP error polling DataForSEO task {task_id}: {e.response.status_code} - {error_text}")
                    if attempt == max_attempts - 1:
                        return {"success": False, "error": f"HTTP {e.response.status_code}: {error_text}"}
                    await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Error polling DataForSEO results for task {task_id}: {str(e)}", exc_info=True)
                if attempt == max_attempts - 1:
                    return {"success": False, "error": str(e)}
                await asyncio.sleep(3)
        
        return {"success": False, "error": "Timeout waiting for results"}
    
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
        
        payload = {
            "data": [{
                "target": domain,
                "max_crawl_pages": max_crawl_pages,
                "enable_javascript": True,
                "load_resources": True,
                "fetch_html": True,
                "respect_robot_txt": False,
                "custom_headers": {"User-Agent": "Mozilla/5.0"}
            }]
        }
        
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

