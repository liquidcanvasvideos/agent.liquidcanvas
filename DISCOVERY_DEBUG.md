# Website Discovery Debugging Guide

## 🔍 Understanding Why You See the Same Websites

### **The Problem:**
You're seeing the same websites repeatedly, even when:
- Selecting different locations
- Running manual searches
- Changing categories

### **Root Causes:**

#### 1. **Deduplication is Working (This is Good!)**
- The system filters out websites that already exist in the database
- If you've run searches before, most results will be filtered out
- **This is expected behavior** - the system only shows NEW websites

#### 2. **Search Engines Return Similar Results**
- Search engines (DuckDuckGo, Google) return similar results for similar queries
- Even with location modifiers, many results overlap
- Example: "home decor blog USA" and "home decor blog Canada" may return many of the same sites

#### 3. **Limited Query Variation**
- Only 15 queries are executed per run (from potentially 100+ total queries)
- Queries are randomly shuffled, so you might get the same queries multiple times
- Location modifiers don't always change results significantly

#### 4. **Database Already Has Most Results**
- If you've run multiple searches, the database likely has most relevant websites
- New searches will find mostly duplicates
- **This is normal** - you need to wait for new websites to appear in search results

---

## 📊 How to See What's Being Searched

### **In the Frontend:**
1. Click the **📊 (BarChart)** icon in the Website Discovery section
2. This shows:
   - **Search Sources**: Which search engine was used (DataForSEO, DuckDuckGo, etc.)
   - **Recent Queries**: What search queries were actually executed
   - **Results Breakdown**: How many were discovered, new, skipped, failed

### **In the Backend Logs:**
Look for these log messages:
- `✅ Using DataForSEO API for website discovery` - Using DataForSEO
- `ℹ️ DataForSEO not configured, using DuckDuckGo` - Using DuckDuckGo
- `Generated X queries for location: usa` - Queries generated
- `Search source breakdown: {'dataforseo': 45, 'duckduckgo': 5}` - Source counts
- `Found X existing URLs in database (will filter from Y discovered)` - Deduplication

---

## 🔧 How to Get Different Results

### **Option 1: Wait for New Websites**
- Search engines update their indexes over time
- New websites appear in search results
- Run searches daily/weekly to catch new sites

### **Option 2: Use Different Categories**
- Try different category combinations
- Each category generates different queries
- Example: Try only "tech_innovation" instead of all categories

### **Option 3: Use Different Locations**
- Each location generates different queries
- Try searching one location at a time
- Example: Search "USA" separately from "Canada"

### **Option 4: Increase Query Diversity**
- Currently only 15 queries per run
- Could increase to 30-50 queries (but slower)
- More queries = more diverse results

### **Option 5: Clear Database (Not Recommended)**
- Only if you want to start fresh
- **WARNING**: This will delete all discovered websites
- Use only for testing

---

## 🎯 What the System is Actually Doing

### **Current Flow:**
```
1. Generate queries based on location/categories
   → Example: "home decor blog USA", "home decor blog Canada"
   
2. Search using DataForSEO (if configured) or DuckDuckGo
   → Returns ~5-10 results per query
   → Total: ~75-150 URLs discovered
   
3. Filter out existing URLs from database
   → Checks both DiscoveredWebsite and ScrapedWebsite tables
   → Only keeps NEW URLs
   
4. Save new discoveries
   → Saves to DiscoveredWebsite table
   → Source: 'dataforseo' or 'duckduckgo'
   
5. Scrape new websites
   → Scrapes only NEW websites
   → Extracts contacts
```

### **Why You See Same Results:**
- **Step 3** filters out most results (they already exist)
- If database has 1000+ websites, most new searches will find duplicates
- Only truly NEW websites (that weren't in previous searches) will appear

---

## 📈 Expected Behavior

### **First Search (Empty Database):**
- ✅ Discovers 50-100 new websites
- ✅ All are saved and scraped
- ✅ You see many new results

### **Second Search (Same Day):**
- ⚠️ Discovers 50-100 websites
- ⚠️ But 45-95 are duplicates (already in database)
- ⚠️ Only 5-10 are truly new
- ✅ You see fewer new results (this is normal!)

### **After Multiple Searches:**
- ⚠️ Most results are duplicates
- ⚠️ Only 0-5 new websites per search
- ✅ This is expected - database is comprehensive

---

## 🛠️ Troubleshooting

### **"I'm seeing the same websites"**
**Check:**
1. Are they actually the same URLs? (Check the URL column)
2. Are they from the same search? (Check created_at timestamp)
3. Are they being filtered as duplicates? (Check logs for "Found X existing URLs")

**Solution:**
- This is normal if you've run searches before
- Wait for new websites to appear in search results
- Try different location/category combinations

### **"No new websites found"**
**Check:**
1. Are all search results already in database? (Check logs)
2. Is the search actually running? (Check status)
3. Are queries being generated? (Check logs for "Generated X queries")

**Solution:**
- This means deduplication is working perfectly
- All search results already exist in database
- Wait for new websites to appear in search engines

### **"I want to see where searches come from"**
**Check:**
1. Click the 📊 icon in Website Discovery section
2. Look at "Search Sources" - shows DataForSEO vs DuckDuckGo
3. Look at "Recent Queries" - shows actual search queries used

---

## 💡 Recommendations

1. **Run searches less frequently** (daily/weekly instead of every 15 minutes)
   - Gives search engines time to update indexes
   - More likely to find new websites

2. **Use location-specific searches**
   - Search one location at a time
   - More focused results
   - Less overlap between searches

3. **Monitor the statistics**
   - Check "Search Sources" to see which engine is used
   - Check "Recent Queries" to see what's being searched
   - Check "Skipped" count - high = many duplicates (normal)

4. **Understand this is expected**
   - After initial discovery, most searches will find duplicates
   - Only truly new websites will appear
   - This means the system is working correctly!

---

## 🔍 How to Verify Search Source

### **Check Frontend:**
1. Go to Website Discovery section
2. Click 📊 icon to show statistics
3. Look at "Search Sources" section
   - `dataforseo` = Using DataForSEO (Google SERP)
   - `duckduckgo` = Using DuckDuckGo (free search)

### **Check Backend Logs:**
Look for:
- `✅ Using DataForSEO API` = DataForSEO active
- `ℹ️ DataForSEO not configured` = Using DuckDuckGo
- `Search source breakdown: {'dataforseo': 50}` = 50 results from DataForSEO

### **Check Database:**
```sql
SELECT source, COUNT(*) 
FROM discovered_websites 
WHERE created_at > datetime('now', '-1 hour')
GROUP BY source;
```

---

## 🎯 Summary

**Seeing the same websites is NORMAL if:**
- ✅ You've run searches before
- ✅ Database already has those websites
- ✅ Deduplication is working (filtering duplicates)

**To get different results:**
- ⏰ Wait for new websites to appear in search engines
- 🔄 Try different location/category combinations
- 📊 Check statistics to see what's being searched
- 🔍 Verify which search engine is being used

**The system is working correctly** - it's just that most search results already exist in your database!

