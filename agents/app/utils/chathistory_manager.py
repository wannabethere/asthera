# Chat history manager
class ChatHistoryManager:
    """Manages chat history for multiple threads."""
    
    def __init__(self):
        self.chat_histories = defaultdict(list)
        self.recommendations_store = {}  # Store recommendations by thread_id
    
    def create_thread(self) -> str:
        """Create a new chat thread.
        
        Returns:
            Thread ID
        """
        thread_id = str(uuid.uuid4())
        self.chat_histories[thread_id] = []
        return thread_id
    
    def add_message(self, thread_id: str, message: ChatMessage) -> None:
        """Add a message to a thread.
        
        Args:
            thread_id: Thread ID
            message: ChatMessage object
        """
        if thread_id not in self.chat_histories:
            raise ValueError(f"Thread {thread_id} does not exist")
        
        self.chat_histories[thread_id].append(message)
    
    def get_history(self, thread_id: str) -> List[ChatMessage]:
        """Get the history for a thread.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            List of ChatMessage objects
        """
        if thread_id not in self.chat_histories:
            raise ValueError(f"Thread {thread_id} does not exist")
        
        return self.chat_histories[thread_id]
    
    def store_recommendations(self, thread_id: str, recommendations: List[KPIRecommendation]) -> None:
        """Store recommendations for a thread.
        
        Args:
            thread_id: Thread ID
            recommendations: List of KPIRecommendation objects
        """
        self.recommendations_store[thread_id] = recommendations
    
    def get_recommendations(self, thread_id: str) -> List[KPIRecommendation]:
        """Get stored recommendations for a thread.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            List of KPIRecommendation objects
        """
        if thread_id not in self.recommendations_store:
            return []
        
        return self.recommendations_store[thread_id]


# Create chat history manager instance
chat_manager = ChatHistoryManager()