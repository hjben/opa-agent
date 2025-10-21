from qdrant_client import QdrantClient as QC

class QdrantService:
    def __init__(self, url):
        self.client = QC(url=url)

    def search(self, collection_name, query_vector, limit=5):
        result = self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit
        )
        return result
