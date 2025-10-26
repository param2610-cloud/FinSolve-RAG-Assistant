# Vercel Deployment Guide

## Overview
This Flask application is configured to run on Vercel using serverless functions.

## Prerequisites
1. Install Vercel CLI: `npm i -g vercel`
2. Create a Vercel account at https://vercel.com

## Project Structure for Vercel
```
├── api/
│   └── index.py          # Vercel serverless function entry point
├── app/                  # Your Flask application
├── vercel.json           # Vercel configuration
├── requirements.txt      # Python dependencies
└── .vercelignore        # Files to ignore during deployment
```

## Local Development
To test the app locally with Vercel:

```bash
vercel dev
```

Your Flask application will be available at `http://localhost:3000`

## Environment Variables
Before deploying, set up your environment variables in Vercel:

1. Go to your project settings on Vercel
2. Navigate to "Environment Variables"
3. Add the following variables:
   - `JWT_SECRET_KEY`: Your JWT secret key
   - `GROQ_API_KEY`: Your Groq API key (if using)
   - Any other environment variables from your `.env` file

Or use the Vercel CLI:
```bash
vercel env add JWT_SECRET_KEY
vercel env add GROQ_API_KEY
```

## Deployment

### Quick Deploy
```bash
vercel
```

### Production Deploy
```bash
vercel --prod
```

### One-Click Deploy
You can also deploy directly from GitHub by clicking:

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/param2610-cloud/FinSolve-RAG-Assistant)

## Important Notes

### Limitations on Vercel
1. **Serverless Function Timeout**: Free tier has 10s timeout, Pro tier has 60s
2. **Cold Starts**: First request may be slower due to serverless nature
3. **File System**: Temporary filesystem, don't rely on persistent storage
4. **Memory Limits**: 1GB on free tier, configurable on Pro tier

### Recommended Changes for Production
1. **External Vector Store**: Instead of local ChromaDB, use:
   - Pinecone
   - Weaviate Cloud
   - Qdrant Cloud

2. **External Database**: Instead of JSON files, use:
   - PostgreSQL (Vercel Postgres)
   - MongoDB Atlas
   - Redis (Upstash)

3. **Object Storage**: For files, use:
   - Vercel Blob
   - AWS S3
   - Cloudflare R2

### Handling Heavy Dependencies
The current setup includes large ML dependencies (spaCy, sentence-transformers). Consider:

1. **Reduce Model Size**: Use smaller models
2. **External API**: Move ML processing to external services
3. **Lazy Loading**: Load models only when needed

### Static Files
Static files are served from the `resources/static` directory. Update paths in `app/__init__.py` if needed.

## Monitoring
After deployment, monitor your app:
- Vercel Dashboard: https://vercel.com/dashboard
- Function Logs: Available in real-time
- Analytics: Built-in performance metrics

## Troubleshooting

### Out of Memory (OOM) During Build
**Error**: "Out of Memory" events detected during build

**Solutions**:
1. **Optimized Requirements** (Already implemented):
   - Removed heavy `langchain` and `langchain-community` packages
   - Using only essential LangChain modules
   - This reduces build memory footprint significantly

2. **Increased Memory Allocation** (Already configured):
   ```json
   {
     "memory": 3008,
     "maxLambdaSize": "250mb"
   }
   ```

3. **Alternative Approach - Split Services**:
   If OOM persists, consider splitting into microservices:
   - Deploy API/Auth on Vercel
   - Deploy ML/RAG components on:
     - Railway.app (supports larger builds)
     - Render.com (native Python support)
     - Google Cloud Run (containerized)
     - AWS Lambda with layers

4. **Use Pre-built Models**:
   - Host vector store externally (Pinecone, Weaviate)
   - Use API-based embeddings (OpenAI, Cohere)
   - Remove spaCy if not critical

5. **Docker Alternative**:
   ```bash
   # Build locally and push to container registry
   docker build -t finsolve-rag .
   # Deploy to Cloud Run, Railway, or Render
   ```

### Deployment Fails
- Check Vercel logs: `vercel logs`
- Ensure all dependencies are in `requirements.txt`
- Verify Python version compatibility (Vercel supports Python 3.9+)

### Function Timeout
- Optimize heavy operations
- Consider using Vercel's Edge Functions for faster response
- Move long-running tasks to background jobs

### Import Errors
- Ensure all required packages are in `requirements.txt`
- Check that your app structure follows Python package conventions
- Verify relative imports are correct

### Build Taking Too Long
- Current optimizations should help
- If still slow, consider:
  - Caching strategy with `vercel.json`
  - Pre-building dependencies in Docker
  - Using lighter alternatives to ML libraries

## Resources
- [Vercel Python Runtime Documentation](https://vercel.com/docs/functions/serverless-functions/runtimes/python)
- [Vercel CLI Documentation](https://vercel.com/docs/cli)
- [Flask Deployment Guide](https://flask.palletsprojects.com/en/3.0.x/deploying/)
