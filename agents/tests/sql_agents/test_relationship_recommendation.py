import logging
import chromadb
from langchain_openai import OpenAIEmbeddings
from app.storage.documents import DocumentChromaStore
from app.settings import get_settings
from app.core.provider import DocumentStoreProvider
from app.agents.nodes.sql.relationship_recommendation import RelationshipRecommendation
from app.agents.nodes.sql.utils.sql_prompts import Configuration
import orjson
import asyncio
from typing import Optional, Dict, Any

logger = logging.getLogger("lexy-ai-service")
settings = get_settings()

class RelationshipRecommendationTest:
    def __init__(self):
        """Initialize the Relationship Recommendation test with necessary components."""
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY
        )
        self.persistent_client = chromadb.PersistentClient(
            path=settings.CHROMA_STORE_PATH
        )
        # Minimal document store for testing
        self.document_stores = {
            "relationship_recommendation": DocumentChromaStore(
                persistent_client=self.persistent_client,
                collection_name="relationship_recommendation"
            )
        }

    async def test_relationship_recommendation(self):
        try:
            # Example data model (MDL) as JSON string
            mdl_dict = {
                "tables": [
                    {
                        "name": "orders",
                        "columns": [
                            {"name": "order_id", "type": "int"},
                            {"name": "customer_id", "type": "int"}
                        ]
                    },
                    {
                        "name": "customers",
                        "columns": [
                            {"name": "customer_id", "type": "int"},
                            {"name": "name", "type": "string"}
                        ]
                    }
                ]
            }
            mdl_json = orjson.dumps(mdl_dict).decode()

            documentProvider = DocumentStoreProvider(stores=self.document_stores)
            recommender = RelationshipRecommendation(doc_store_provider=documentProvider)

            test_id = "test-relationship-recommendation-1"
            input_obj = RelationshipRecommendation.Input(
                id=test_id,
                mdl=mdl_json,
                configuration=Configuration(language="English")
            )

            logger.info("Testing RelationshipRecommendation.recommend() with sample MDL")
            result = await recommender.recommend(input_obj)
            logger.info("Relationship Recommendation Result:")
            logger.info(result)
            print(result)
            return result
        except Exception as e:
            logger.error(f"Error in relationship recommendation test: {str(e)}")
            raise

async def main():
    try:
        test = RelationshipRecommendationTest()
        logger.info("Starting Relationship Recommendation test")
        result = await test.test_relationship_recommendation()
        if result:
            logger.info("\nRelationship Recommendation Test Summary:")
            logger.info(f"Status: {result.status}")
            if result.response:
                logger.info(f"Response: {result.response}")
            if result.error:
                logger.info(f"Error: {result.error}")
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 