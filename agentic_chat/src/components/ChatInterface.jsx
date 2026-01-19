import { useState, useRef, useEffect } from 'react'
import MessageList from './MessageList'
import MessageInput from './MessageInput'
import './ChatInterface.css'

function ChatInterface({ messages, onSendMessage, onClearChat, isStreaming, disabled }) {
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const formatTime = (date) => {
    return date.toLocaleTimeString('en-US', { 
      hour: 'numeric', 
      minute: '2-digit',
      hour12: true 
    })
  }

  return (
    <div className="chat-interface">
      <div className="chat-header">
        <h2>AI Assistant</h2>
        <button 
          onClick={onClearChat} 
          className="new-chat-button"
          disabled={messages.length === 0}
        >
          + New Chat
        </button>
      </div>
      
      {messages.length > 0 && (
        <div className="chat-timestamp">
          {formatTime(messages[0].timestamp)}
        </div>
      )}
      
      <MessageList 
        messages={messages} 
        isStreaming={isStreaming}
        messagesEndRef={messagesEndRef}
      />
      
      <div className="chat-footer">
        <MessageInput 
          onSendMessage={onSendMessage} 
          disabled={disabled || isStreaming}
          isStreaming={isStreaming}
        />
        <div className="chat-hint">
          Press Enter to send, Shift+Enter for new line
        </div>
      </div>
    </div>
  )
}

export default ChatInterface

