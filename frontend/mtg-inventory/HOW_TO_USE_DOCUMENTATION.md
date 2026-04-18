# 🔍 How to Use This API Documentation

Welcome! This guide explains how to navigate and use the API documentation for MTG Inventory System.

---

## 📍 You Are Here

You have **5 comprehensive documentation files** to support different workflows:

```
Your Question
      ↓
Choose Right File
      ↓
Find Your Answer
      ↓
Complete Your Task
```

---

## 🎯 Choose Your File Based on Your Task

### **Task: I want to QUICKLY find endpoint details**

→ Open **`API_QUICK_REFERENCE.md`**

This file is a condensed reference with:
- Quick endpoint list
- cURL examples
- Common query parameters
- Status code meanings
- Common workflows

**Example use case**: "What's the endpoint to search cards?"
1. Open `API_QUICK_REFERENCE.md`
2. Search for "search"
3. Find: `GET /api/cards/search?q=<query>`
4. Use it!

---

### **Task: I want COMPLETE DETAILS about an endpoint**

→ Open **`API_CONTRACT.md`**

This is the comprehensive specification with:
- Full endpoint descriptions
- All request parameters with explanations
- Example requests and responses
- Error codes and meanings
- Data model definitions
- Complete workflow examples

**Example use case**: "How do I handle errors from the search endpoint?"
1. Open `API_CONTRACT.md`
2. Go to "Error Handling" section
3. Find error response format
4. See examples
5. Understand how to handle

---

### **Task: I want to TEST endpoints interactively**

→ Open/Import **`postman_collection.json`** into Postman

This file contains:
- 20+ pre-configured requests
- Ready-to-use headers and bodies
- Variables for easy customization
- Examples for each endpoint
- Organized by resource type

**Example use case**: "Let me test the search endpoint"
1. Download [Postman](https://www.postman.com/downloads/) if needed
2. Open Postman
3. File → Import → Choose `postman_collection.json`
4. Set `{{base_url}}` = `http://localhost:5000`
5. Find "Search Cards" request under "Cards" folder
6. Click **Send**
7. See response

---

### **Task: I want to AUTO-GENERATE code or integrate with tools**

→ Use **`openapi.yaml`**

This is a standardized OpenAPI 3.0 specification that works with:
- Code generators (Python, JS, Go, etc.)
- API documentation tools (Swagger UI, ReDoc)
- Automation tools
- API mocking tools

**Example use case**: "Generate a Python client library"
1. Install: `pip install openapi-generator`
2. Run: `openapi-generator-cli generate -i openapi.yaml -g python-client -o ./client`
3. Use generated client in your code

---

### **Task: I want to VISUALIZE the API**

→ Use **`openapi.yaml`** with Swagger UI or ReDoc

**Option 1: Online (No Installation)**
1. Visit https://editor.swagger.io
2. File → Import → `openapi.yaml`, choose file
3. See interactive documentation
4. Click "Try it out" on any endpoint

**Option 2: Local Swagger UI**
```bash
docker run -p 8080:8080 -v $(pwd)/openapi.yaml:/openapi.yaml \
  swaggerapi/swagger-ui -e SWAGGER_JSON=/openapi.yaml
```
Then visit http://localhost:8080

**Option 3: ReDoc**
```bash
npx redoc-cli serve openapi.yaml
```
Then visit http://localhost:8080

---

## 📊 File Comparison

| Need | File | Format | Best For |
|------|------|--------|----------|
| Quick answers | API_QUICK_REFERENCE.md | Markdown | Developers, cheat sheet |
| Complete details | API_CONTRACT.md | Markdown | Learning, understanding|
| Interactive testing | postman_collection.json | Postman | QA, manual testing | 
| Tool integration | openapi.yaml | OpenAPI 3.0 | Automation, code gen |
| Visualization | openapi.yaml | OpenAPI 3.0 | Visual learners |

---

## 🔄 Example Workflows

### Workflow 1: Understanding an Endpoint (5 minutes)

1. **Quick lookup**: Check `API_QUICK_REFERENCE.md` for endpoint
2. **Get details**: Read full description in `API_CONTRACT.md`
3. **See example**: Find example request/response in `API_CONTRACT.md`
4. **Test it**: Open Postman request in `postman_collection.json`
5. **Execute**: Click Send and see real response

### Workflow 2: Integrating with Your App (15 minutes)

1. **Choose language**: Node.js, Python, Go, etc.
2. **Generate client**: Use `openapi.yaml` with code generator
3. **Install generated library**: `pip install generated_client`
4. **Use in code**: Import and call generated functions
5. **Test**: Run against live API

### Workflow 3: API Testing (30 minutes)

1. **Import collection**: Load `postman_collection.json` into Postman
2. **Configure variables**: Set `base_url` and `auth_token`
3. **Run requests**: Test each endpoint individually
4. **Check responses**: Verify data format matches contract
5. **Test edge cases**: Use `API_CONTRACT.md` to find error scenarios
6. **Report issues**: Document findings against contract

### Workflow 4: API Learning (1-2 hours)

1. **Start here**: Read this file (5 min)
2. **Overview**: Read `API_DOCUMENTATION_INDEX.md` (10 min)
3. **Quick ref**: Skim `API_QUICK_REFERENCE.md` (10 min)
4. **Full spec**: Read `API_CONTRACT.md` sections in order (30-45 min)
5. **Visualize**: Import `openapi.yaml` into Swagger UI (15 min)
6. **Practice**: Test with Postman collection (20 min)

---

## 🎓 Documentation Sections Guide

### API_QUICK_REFERENCE.md Sections

```markdown
1. Documentation Files - Overview of all files
2. Quick Start - Get started immediately
3. Common Endpoints - Most-used endpoints
4. Request Examples - cURL examples
5. Response Format - How responses look
6. Status Codes - What codes mean
7. Query Parameters - How to filter/paginate
8. Card Conditions - Valid condition codes
9. Data Fields - What fields mean
10. Pagination - How pagination works
11. Debugging Tips - How to debug
12. FAQ - Common questions
```

→ **Use for**: Finding quick answers

### API_CONTRACT.md Sections

```markdown
1. Overview - What this is
2. Authentication - How to authenticate
3. Common Headers - What headers to send
4. Error Handling - How errors work
5. Status Codes - Complete list
6. Endpoints by Resource:
   - Health & System
   - Cards
   - Inventory Management
   - Locations & Boxes
   - Pricing
   - eBay Integration
7. Data Models - Detailed field documentation
8. Examples - Complete workflow examples
9. Authentication Details - For future use
10. Rate Limiting - For future use
11. Changelog - What changed
```

→ **Use for**: Complete understanding

### openapi.yaml Sections

```yaml
info: - Version and general info
servers: - Base URLs
paths: - All endpoints and operations
components: - Data schemas and responses
securitySchemes: - Authentication setup
tags: - Endpoint grouping
```

→ **Use for**: Tool integration, code generation, visualization

### postman_collection.json Structure

```json
{
  "info": { ... },
  "item": [
    {
      "name": "System",
      "item": [
        { "name": "Health Check", "request": {...} }
      ]
    },
    {
      "name": "Cards",
      "item": [
        { "name": "Search Cards", "request": {...} },
        { "name": "Get Card by ID", "request": {...} },
        ...
      ]
    },
    ...
  ],
  "variable": [
    { "key": "base_url", "value": "http://localhost:5000" },
    { "key": "auth_token", "value": "" }
  ]
}
```

→ **Use for**: Interactive testing in Postman

---

## 🔑 Key Information Quick Lookup

### "Where do I find...?"

| What | Location |
|------|----------|
| List of all endpoints | API_QUICK_REFERENCE.md → "Common Endpoints" |
| Endpoint details | API_CONTRACT.md → "Endpoints by Resource" |
| Request body format | API_CONTRACT.md → specific endpoint section |
| Response format | API_CONTRACT.md → "Response Format" |
| Error handling | API_CONTRACT.md → "Error Handling" section |
| Status codes | API_QUICK_REFERENCE.md → "Status Codes" table |
| Authentication info | API_CONTRACT.md → "Authentication" |
| Examples | API_CONTRACT.md → "Examples" section |
| Postman requests | postman_collection.json → Import into Postman |
| cURL examples | API_QUICK_REFERENCE.md → "Request Examples" |

---

## 💡 Tips for Using This Documentation

### Tip 1: Use Search/Find Function
- Press `Ctrl+F` (Windows) or `Cmd+F` (Mac)
- Search for endpoint name or field name
- Jump directly to relevant section

### Tip 2: Keep Multiple Windows Open
1. Browser tab 1: API_QUICK_REFERENCE.md
2. Browser tab 2: API_CONTRACT.md (details)
3. App window: Postman (testing)
4. IDE: Your code

### Tip 3: Bookmark Common Sections
- Endpoints you use frequently
- Error codes table
- Response format examples

### Tip 4: Use Postman for Learning
- Import collection
- Look at each request's structure
- Click "Send" to see actual responses
- Compare with documentation

### Tip 5: Print Quick Reference
- Print `API_QUICK_REFERENCE.md`
- Keep it on your desk
- Faster than searching online

---

## ✅ Getting Started Checklist

- [ ] Read this file (5-10 min)
- [ ] Skim API_DOCUMENTATION_INDEX.md (5 min)
- [ ] Bookmark API_QUICK_REFERENCE.md (quick lookups)
- [ ] Download [Postman](https://www.postman.com/downloads/)
- [ ] Import postman_collection.json into Postman
- [ ] Test `/api/health` endpoint first
- [ ] Read relevant section of API_CONTRACT.md for your task
- [ ] Test your endpoint in Postman
- [ ] Integrate into your application

---

## 🛠️ Tools You'll Need

### Option 1: Minimal (Just Browser)
- Web browser (Chrome, Firefox, Safari, Edge)
- Text editor or IDE
- cURL (usually pre-installed)

### Option 2: Recommended (Developer)
- Postman (free version sufficient)
- Web browser
- IDE/Text editor
- Terminal/Command Prompt

### Option 3: Full Setup (Professional)
- Postman (paid enterprise features)
- VSCode or JetBrains IDE
- Docker (for tools)
- Language-specific SDKs (Python, JS, etc.)

---

## 🚨 Common Starting Mistakes to Avoid

❌ **Mistake 1**: Reading all documentation before getting started
✅ **Solution**: Use quick reference first, dive deeper as needed

❌ **Mistake 2**: Testing without reading error handling section
✅ **Solution**: Always read error codes before testing

❌ **Mistake 3**: Not checking pagination requirements
✅ **Solution**: Understand pagination before building list features

❌ **Mistake 4**: Ignoring required fields
✅ **Solution**: Check "Required" column in parameter tables

❌ **Mistake 5**: Using wrong header format
✅ **Solution**: Copy headers from examples, don't guess

---

## 🎓 Next Steps After Reading This

1. **Immediate** (Next 5 min):
   - Close this file
   - Open API_QUICK_REFERENCE.md
   - Find your first endpoint

2. **Short-term** (Next 30 min):
   - Import Postman collection
   - Test 3-5 endpoints
   - Compare with documentation

3. **Medium-term** (Next 1-2 hours):
   - Read API_CONTRACT.md sections relevant to your task
   - Test complex workflows in Postman
   - Start coding integration

4. **Long-term** (Ongoing):
   - Refer back to quick reference for common tasks
   - Bookmark sections you use frequently
   - Generate client code for your language

---

## 📞 Getting Help

**If you can't find something:**
1. Try searching with Ctrl+F
2. Check the Table of Contents
3. Look in related sections
4. Check the FAQ in quick reference
5. Test in Postman to see actual behavior

**If something seems wrong:**
1. Check API_CONTRACT.md for expected format
2. Verify your request matches examples
3. Check response against error section
4. Review status codes

---

## 📚 Documentation Hierarchy

```
You (Reading this)
    ↓
API_QUICK_REFERENCE.md (Fast answers)
    ↓
API_CONTRACT.md (Complete details)
    ↓
openapi.yaml (Machine readable)
    ↓
postman_collection.json (Interactive testing)
```

Start at top. Go deeper when needed.

---

## 🎯 Success Criteria

You've successfully understood this documentation when you can:

- [ ] Quickly find any endpoint using quick reference
- [ ] Understand what fields are required for any request
- [ ] Predict response format before calling endpoint
- [ ] Handle errors appropriately in your code
- [ ] Use Postman to test any endpoint
- [ ] Generate code from openapi.yaml
- [ ] Explain API structure to teammates

---

**Now go forth and build awesome integrations!** 🚀

For questions or issues, refer back to the appropriate documentation file using the guidance in this file.

**Happy API Development!** 

---

*Document Version: 1.0*  
*Created: March 4, 2026*  
*API Version: 0.1.0*
