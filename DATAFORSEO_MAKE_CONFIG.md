# DataForSEO on_page/task_post - Make.com Configuration Guide

## Problem Analysis

The issue is that Make.com is returning raw response data instead of parsed JSON. This happens when:
1. "Parse response" is set to OFF
2. The response body is being treated as a string instead of JSON

## ✅ CORRECT Make.com HTTP Module Configuration

### Basic Settings
- **URL**: `https://api.dataforseo.com/v3/on_page/task_post`
- **Method**: `POST`
- **Authentication**: `Basic Auth`
  - **Username**: Your DataForSEO login
  - **Password**: Your DataForSEO password

### Request Settings
- **Body type**: `Raw`
- **Content-Type**: `application/json` (Make should auto-detect this)
- **Parse response**: ✅ **ON** (CRITICAL - must be enabled!)
- **Serialized URL**: ❌ **OFF** (not needed for this endpoint)

### Headers
Make.com should automatically add `Content-Type: application/json` when you select "Raw" body type. You can also add it manually:
- **Name**: `Content-Type`
- **Value**: `application/json`

## ✅ CORRECT Request Body (JSON)

**IMPORTANT**: DataForSEO expects a **direct JSON array**, NOT wrapped in a "data" key!

```json
[
  {
    "target": "{{12.domain}}",
    "max_crawl_pages": 5,
    "enable_javascript": true,
    "load_resources": true,
    "fetch_html": true,
    "respect_robot_txt": false,
    "custom_headers": {
      "User-Agent": "Mozilla/5.0"
    }
  }
]
```

### Why This Format?

Based on our working backend implementation, DataForSEO v3 API expects:
- ✅ **Direct array**: `[{...}]`
- ❌ **NOT wrapped**: `{"data": [{...}]}`

## Expected Response Structure

When "Parse response" is ON, Make will return a parsed JSON object like:

```json
{
  "version": "0.1.20251127",
  "status_code": 20000,
  "status_message": "Ok.",
  "time": "0.0280 sec.",
  "cost": 0.0006,
  "tasks_count": 1,
  "tasks_error": 0,
  "tasks": [
    {
      "id": "11301803-1234-0066-0000-d5782c9b63b4",
      "status_code": 20100,
      "status_message": "Task Created.",
      "time": "0.0083 sec.",
      "cost": 0.0006,
      "result_count": 0,
      "result": null
    }
  ]
}
```

## Extracting the Task ID

Once the response is parsed, extract the task ID using:

**Path**: `tasks[0].id`

Or in Make's JSON path notation:
```
{{1.tasks[0].id}}
```

## Troubleshooting

### Issue: "Data: long string" instead of JSON

**Cause**: "Parse response" is set to OFF

**Fix**: 
1. Open the HTTP module settings
2. Find "Parse response" toggle
3. Turn it **ON**
4. Save and re-run the scenario

### Issue: Status 200 but can't access response fields

**Cause**: Response is not being parsed as JSON

**Fix**:
1. Ensure "Parse response" is ON
2. Check that Content-Type header is `application/json`
3. Verify the response body is valid JSON (check DataForSEO API status)

### Issue: "POST Data Is Invalid" error

**Cause**: Payload format is incorrect

**Fix**:
- Ensure the request body is a **direct array** `[{...}]`
- Do NOT wrap it in `{"data": [{...}]}`
- Verify all boolean values are `true`/`false` (not strings)

## Complete Make.com Module Configuration

```
┌─────────────────────────────────────────┐
│ HTTP Module Configuration                │
├─────────────────────────────────────────┤
│ URL: https://api.dataforseo.com/v3/     │
│      on_page/task_post                   │
│ Method: POST                             │
│ Authentication: Basic Auth               │
│   Username: [Your DataForSEO Login]     │
│   Password: [Your DataForSEO Password]   │
├─────────────────────────────────────────┤
│ Body Type: Raw                           │
│ Content-Type: application/json            │
│ Parse response: ✅ ON                    │
│ Serialized URL: ❌ OFF                   │
├─────────────────────────────────────────┤
│ Request Body:                             │
│ [                                        │
│   {                                      │
│     "target": "{{12.domain}}",          │
│     "max_crawl_pages": 5,                │
│     "enable_javascript": true,           │
│     "load_resources": true,              │
│     "fetch_html": true,                  │
│     "respect_robot_txt": false,          │
│     "custom_headers": {                 │
│       "User-Agent": "Mozilla/5.0"       │
│     }                                    │
│   }                                      │
│ ]                                        │
└─────────────────────────────────────────┘
```

## Verification Steps

1. **Test the request** with "Parse response" ON
2. **Check the response** - you should see a JSON object, not a string
3. **Extract task ID** using `{{1.tasks[0].id}}`
4. **Verify status_code** is `20000` (success)

## Additional Notes

- DataForSEO uses Basic Auth (username + password)
- The API returns status code 200 even for API-level errors
- Check `status_code` field: `20000` = success, other codes = error
- Task status `20100` means "Task Created" - this is success, not an error
- Use the task ID to poll `task_get` endpoint for results

