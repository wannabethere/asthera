# OpenAI API Key Setup Instructions

## Issue Found
The hardcoded OpenAI API key in `genieml/agents/app/settings.py` line 74 is invalid or expired, causing a 401 error.

## Solutions

### Option 1: Set Environment Variable (Recommended)
```bash
# Set the environment variable before running your script
export OPENAI_API_KEY="your_actual_openai_api_key_here"

# Then run your script
python genieml/agents/tests/demo_askandquestion_recommendation.py
```

### Option 2: Set Environment Variable in Same Command
```bash
# Set and run in one command
OPENAI_API_KEY="your_actual_openai_api_key_here" python genieml/agents/tests/demo_askandquestion_recommendation.py
```

### Option 3: Create .env File
1. Create a file named `.env` in the `genieml/agents/` directory
2. Add this line to the file:
   ```
   OPENAI_API_KEY=your_actual_openai_api_key_here
   ```
3. Replace `your_actual_openai_api_key_here` with your real OpenAI API key

### Option 4: Update settings.py (Not Recommended)
If you must update the settings file directly, replace the hardcoded key on line 74 with your actual API key.

## How to Get Your OpenAI API Key

1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Sign in to your account
3. Go to API Keys section
4. Create a new API key
5. Copy the key (it starts with `sk-`)

## Verify Your API Key

Test your API key with a simple curl command:
```bash
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer YOUR_API_KEY_HERE"
```

If it returns a list of models, your key is working.

## Security Notes

- Never commit API keys to version control
- Use environment variables or .env files
- .env files should be in .gitignore
- Rotate API keys regularly

## Current Issues Fixed

1. ✅ Fixed method signature error in `_reason_sql_internal` calls
2. ✅ Fixed KeyError for recommendations in demo script
3. ⚠️ Need to set valid OpenAI API key

## Next Steps

1. Set your OpenAI API key using one of the methods above
2. Run the demo script again
3. The method signature errors should be resolved
4. The recommendations KeyError should be handled gracefully 