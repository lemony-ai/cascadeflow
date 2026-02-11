'use client';

import { useChat } from '@ai-sdk/react';
import { useState } from 'react';

export default function Page() {
  const { messages, sendMessage, status } = useChat();

  const [input, setInput] = useState('');
  const isLoading = status === 'submitted' || status === 'streaming';

  return (
    <main className="page">
      <div className="container">
        <header className="header">
          <h1>cascadeflow + Vercel AI SDK</h1>
          <p>Streaming chat powered by cascadeflow cascades.</p>
        </header>

        <section className="card">
          <div className="messages">
            {messages.length === 0 ? (
              <p className="placeholder">Ask a question to start the cascade.</p>
            ) : (
              messages.map((message) => (
                <div key={message.id} className="message">
                  <p className="role">{message.role}</p>
                  <p className="content">
                    {message.parts
                      .filter((part) => part.type === 'text')
                      .map((part) => part.text)
                      .join('')}
                  </p>
                </div>
              ))
            )}
          </div>
        </section>

        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const text = input.trim();
            if (!text || isLoading) return;
            await sendMessage({ text });
            setInput('');
          }}
          className="input-row"
        >
          <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask cascadeflow..." />
          <button type="submit" disabled={isLoading}>
            {isLoading ? 'Thinking...' : 'Send'}
          </button>
        </form>
      </div>
    </main>
  );
}
