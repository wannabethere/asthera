𝗦𝗲𝗲 Ingest data from any source. Machine generated or human generated. The human generated stuff, sadly, usually needs more investigation.

𝗨𝗻𝗱𝗲𝗿𝘀𝘁𝗮𝗻𝗱 This is where autonomy matters. Extract entities (IOCs, assets, identities). Enrich them. Search for context wherever needed. Correlate. Deduplicate cases. All without me babysitting it.

𝗗𝗲𝗰𝗶𝗱𝗲 Reason based on what it knows about my environment and past cases. Give me a verdict: true positive, false positive, or inconclusive. I actually like inconclusive as an option. It usually means something is broken or you don't have enough context. If the system can't answer the 5Ws for me, say so.
Adjust severity. Surface risk indicators. Recommend actions. At this point I want to step in, use a copilot to pivot back if needed, understand something better, or run response actions (including additional enrichment) directly from the platform.

𝗔𝗰𝘁This is where Rafał Kitab made a good point on his post. Even if is the case that the response happens in ITSM , chat or email from here forward. I want to raise tickets where needed. 

Someone responded? Grab that update and bring it back to me I don;t want to leave my case view. Close the loop.






TODO: ADD EVAL for each of the assistant responses.
ADD Decide data to make the agent responses actionable.
ADD LLM Config and .env file to extract
ADD LLM Model config so we can pick different models.



Lets create a series of Workforce Assistants
-- 1. Product Assistants
       -- They mainly look at the product docs, using product help docs from source links that are provided, we will look api doc links, some product docs that are available in chroma
       -- Based on the question it will look for relevant docs from the web, as well as the chroma document edges 
       -- The process is it will recieve the available and then build some questions based on the docs, input question to fetch the relevant contextual edges 
       -- It will also use domain knowledge, User Actions, Policy docs, Key words, concepts, evidences etc
       -- Once fetched it will compose.
       -- Returns a summary of retrieved information or json with a list of documents with summary
       
-- 2. Compliance Assistant
    Similar to Product assistant, but here it will primarily web data with docs relevant to the question from the compliance, controls, policies,

       -- Based on the question it will look for relevant docs from the web, as well as the chroma document edges 
       -- The process is it will recieve the available and then build some questions based on the docs, input question to fetch the relevant contextual edges 
       -- It will also use domain knowledge, User Actions, product knowledge using web or docs from product store
       -- Once fetched it will compose.
       -- Returns a summary of retrieved information or json with a list of documents with summary 

       -- The summary will use the TSC hierarchy to answer.

-- 3. Domain Knowledge
   Similar to other assistants, but here it will primarily web data with docs relevant to the question from the domains and web 
     -- but relies on User Actions, product knowledge User Actions, Policy docs, Key words, concepts, evidences etc using web or docs
      and do the same

-- 4. User Actions (I will decide this later lets create a place holder for this)

***Important
All of them will use the same contextual breakdown for generic but we will pass the configuration for each
-- Web can be considered a tool for searching
-- configuration will include a model for each action, System prompt from a static python file, Human message prompt will be variables, for each action
-- Finally the data sources that will be used for contextual edges and breakdown-- Each data source will have a category breakdown.










