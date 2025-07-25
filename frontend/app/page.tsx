'use client';

import { useState, FormEvent, useRef, useEffect } from 'react';
import styles from './style/home.module.css';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}


export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const chatContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const newUserMessage: Message = { role: 'user', content: input };
    setMessages(prevMessages => [...prevMessages, newUserMessage]);
    const userQuery = input;
    setInput('');
    setLoading(true);

    const initialAssistantMessage: Message = { role: 'assistant', content: '' };
    setMessages(prevMessages => [...prevMessages, initialAssistantMessage]);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL;
      const response = await fetch(`${apiUrl}/ask`, { 
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question: userQuery }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`Failed to fetch response: ${response.status} ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      let accumulatedContent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          console.log('Stream complete');
          break;
        }

        const chunk = decoder.decode(value, { stream: true });
        console.log('Received chunk:', chunk);

        const lines = chunk.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            let dataContent = line.substring(6);

          
            dataContent = dataContent.replace(/([.?!])\s*(A\)|B\)|C\)|D\))/g, '$1\n$2'); 
            dataContent = dataContent.replace(/([^\n\d])(A\)|B\)|C\)|D\))/g, '$1\n$2');

            dataContent = dataContent.replace(/([A-D]\)\s*[^A-Z\n]*)([B-D]\))/g, '$1\n$2');

            dataContent = dataContent.replace(/(D\)\s*[^.\n]*)\s*(\d+\.\s*)/g, '$1\n\n$2');

            accumulatedContent += dataContent;

            setMessages(prevMessages => {
              const lastMessage = prevMessages[prevMessages.length - 1];
              if (lastMessage && lastMessage.role === 'assistant') {
                return [
                  ...prevMessages.slice(0, -1),
                  { ...lastMessage, content: accumulatedContent }
                ];
              }
              return prevMessages;
            });
          }
        }
      }

    } catch (error) {
      console.error('Error fetching RAG response:', error);
      setMessages(prevMessages => {
        const lastMessage = prevMessages[prevMessages.length - 1];
        if (lastMessage && lastMessage.role === 'assistant') {
          return [
            ...prevMessages.slice(0, -1),
            { ...lastMessage, content: `Error: Could not stream response. Details: ${(error as Error).message}` }
          ];
        }
        return [...prevMessages, { role: 'assistant', content: `Error: Could not stream response. Details: ${(error as Error).message}` }];
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <h1 className={styles.header}>WAEC PAST QUESTIONS AI-ASSISTANT</h1>
      <div className={styles.chatBox} ref={chatContainerRef}>
        {messages.length === 0 && (
          <div className={styles.emptyState}>
            Welcome! Ask me for WAEC past questions.
          </div>
        )}
        {messages.map((msg, index) => (
          <div key={index} className={`${styles.message} ${msg.role === 'user' ? styles.userMessage : styles.assistantMessage}`}>
            <div className={styles.messageContent}>
              <p>{msg.content}</p>
            </div>
          </div>
        ))}
        {loading && (
          <div className={`${styles.message} ${styles.assistantMessage}`}>
            <div className={styles.messageContent}>
              <p>Thinking...</p>
            </div>
          </div>
        )}
      </div>
      <form className={styles.inputForm} onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about past questions..."
          className={styles.inputField}
          disabled={loading}
        />
        <button type="submit" className={styles.sendButton} disabled={loading}>
          Send
        </button>
      </form>
    </div>
  );
}