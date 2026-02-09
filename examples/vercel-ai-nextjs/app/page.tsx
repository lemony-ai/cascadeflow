'use client';

import { useChat } from '@ai-sdk/react';

export default function Page() {
  const { messages, input, handleInputChange, handleSubmit, isLoading } = useChat({
    api: '/api/chat',
  });

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
                  <p className="content">{message.content}</p>
                </div>
              ))
            )}
          </div>
        </section>

        <form onSubmit={handleSubmit} className="input-row">
          <input value={input} onChange={handleInputChange} placeholder="Ask cascadeflow..." />
          <button type="submit" disabled={isLoading}>
            {isLoading ? 'Thinking...' : 'Send'}
          </button>
        </form>
      </div>
    </main>
  );
}

