import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Wrench, Bot, User, ShieldAlert } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ChatMessage } from '../types';

interface Props {
  messages: ChatMessage[];
  isLoading: boolean;
  onSendMessage: (message: string) => void;
}

export function ChatPanel({ messages, isLoading, onSendMessage }: Props) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;
    onSendMessage(trimmed);
    setInput('');
    if (inputRef.current) inputRef.current.style.height = 'auto';
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    // Auto-resize
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  };

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center max-w-md">
              <Bot className="w-12 h-12 mx-auto mb-4 text-accent/40" />
              <h2 className="text-lg font-semibold text-gray-300 mb-2">Fraud Detection Assistant</h2>
              <p className="text-sm text-gray-500 leading-relaxed">
                I can help you investigate suspicious transactions, analyze fraud patterns,
                explain model predictions, and surface risk insights. Try asking:
              </p>
              <div className="mt-4 space-y-2">
                {[
                  '"Show me the fraud risk dashboard"',
                  '"Investigate user 150 for suspicious activity"',
                  '"Score transaction 5423 and explain why"',
                ].map(suggestion => (
                  <button
                    key={suggestion}
                    onClick={() => onSendMessage(suggestion.replace(/"/g, ''))}
                    className="block w-full text-left px-3 py-2 text-xs text-gray-400
                               bg-surface-2 rounded-lg border border-surface-4
                               hover:border-accent/30 hover:text-gray-300"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}

        {isLoading && (
          <div className="flex items-start gap-3 animate-fade-slide-in">
            <div className="p-1.5 bg-accent/10 rounded-lg mt-0.5">
              <Bot className="w-4 h-4 text-accent" />
            </div>
            <div className="bg-surface-2 rounded-xl rounded-tl-sm px-4 py-3">
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <Loader2 className="w-4 h-4 animate-spin" />
                Analyzing...
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="px-4 pb-4">
        <div className="flex items-end gap-2 bg-surface-2 border border-surface-4 rounded-xl px-3 py-2
                        focus-within:border-accent/50 focus-within:ring-1 focus-within:ring-accent/20">
          <textarea
            ref={inputRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask about transactions, fraud patterns, or risk analysis..."
            rows={1}
            className="flex-1 bg-transparent text-sm text-gray-200 placeholder-gray-600
                       outline-none resize-none max-h-[120px]"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="p-2 text-gray-400 hover:text-accent disabled:opacity-30
                       disabled:cursor-not-allowed rounded-lg hover:bg-surface-3"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex items-start gap-3 animate-fade-slide-in ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`p-1.5 rounded-lg mt-0.5 flex-shrink-0
        ${isUser ? 'bg-accent/10' : 'bg-accent/10'}`}>
        {isUser
          ? <User className="w-4 h-4 text-accent" />
          : <Bot className="w-4 h-4 text-accent" />}
      </div>
      <div className={`max-w-[85%] space-y-2 ${isUser ? 'items-end' : ''}`}>
        {/* Llama Guard block notice */}
        {message.guard && !message.guard.safe && (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-fraud-red/10 rounded-lg text-xs">
            <ShieldAlert className="w-3 h-3 text-fraud-red flex-shrink-0" />
            <span className="text-fraud-red font-medium">Blocked by Llama Guard</span>
            {message.guard.category_names && (
              <span className="text-gray-500 truncate">{message.guard.category_names}</span>
            )}
          </div>
        )}

        {/* Tool call indicators */}
        {message.tool_calls && message.tool_calls.length > 0 && (
          <div className="space-y-1">
            {message.tool_calls.map((tc, i) => (
              <div key={i} className="flex items-center gap-2 px-3 py-1.5 bg-surface-3/50 rounded-lg text-xs">
                <Wrench className="w-3 h-3 text-fraud-amber flex-shrink-0" />
                <span className="text-fraud-amber font-medium">{formatToolName(tc.tool)}</span>
                <span className="text-gray-500 truncate">{tc.result_summary}</span>
              </div>
            ))}
          </div>
        )}

        {/* Message content */}
        <div className={`px-4 py-3 rounded-xl text-sm leading-relaxed
          ${isUser
            ? 'bg-accent text-white rounded-tr-sm'
            : 'bg-surface-2 text-gray-300 rounded-tl-sm'
          }`}>
          <div className="prose prose-invert prose-sm max-w-none
                          prose-p:my-1 prose-li:my-0.5 prose-headings:mb-1 prose-headings:mt-2
                          prose-code:text-accent prose-code:bg-surface-3 prose-code:px-1 prose-code:rounded
                          prose-pre:bg-surface-3 prose-pre:rounded-lg
                          prose-table:my-2 prose-table:text-xs
                          prose-thead:border-surface-4
                          prose-th:px-3 prose-th:py-1.5 prose-th:text-gray-300 prose-th:font-semibold
                          prose-td:px-3 prose-td:py-1.5
                          prose-tr:border-surface-4">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                // Wide tables scroll inside the bubble instead of breaking the layout
                table: ({ children }) => (
                  <div className="overflow-x-auto rounded-lg border border-surface-4">
                    <table className="min-w-full">{children}</table>
                  </div>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatToolName(name: string): string {
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}
