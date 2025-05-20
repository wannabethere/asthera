import { createContext, useContext, useState } from "react"

const ConversationContext = createContext();

export const ConversationProvider = ({ children }) => {
    const [conversations, setConversations] = useState([]);

    const value = {
        conversations,
        setConversations,
    };

    return (
        <ConversationContext.Provider value={value}>
            {children}
        </ConversationContext.Provider>
    )
}

// export const useConversation =  useContext(ConversationContext) Single Line

export const useConversation = () => {
    const conversationContext = useContext(ConversationContext);
    if (!conversationContext) {
        throw new Error('useConversation must be used within a ConversationProvider');
    }
    return conversationContext
}