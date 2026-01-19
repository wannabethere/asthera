import { useState, useRef, useEffect } from 'react'
import './MessageInput.css'

function MessageInput({ onSendMessage, disabled, isStreaming }) {
  const [input, setInput] = useState('')
  const textareaRef = useRef(null)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (input.trim() && !disabled) {
      onSendMessage(input.trim())
      setInput('')
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
      }
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const handleChange = (e) => {
    setInput(e.target.value)
    // Auto-resize textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`
    }
  }

  useEffect(() => {
    if (textareaRef.current && input === '') {
      textareaRef.current.style.height = 'auto'
    }
  }, [input])

  return (
    <form className="message-input" onSubmit={handleSubmit}>
      <textarea
        ref={textareaRef}
        value={input}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={disabled ? "Select an assistant and dataset first" : "Type your message..."}
        disabled={disabled || isStreaming}
        className="input-field"
        rows={1}
      />
      <button 
        type="submit" 
        disabled={disabled || isStreaming || !input.trim()}
        className="send-button"
      >
        {isStreaming ? 'Sending...' : 'Send'}
      </button>
    </form>
  )
}

export default MessageInput

