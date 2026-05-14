import React, { useMemo, useRef, useState } from 'react';
import { getPageData } from '../lib/data';
import { PageLayout } from '../components/Sidebar';

type Source = 'vector_db' | 'llm' | 'local_error' | null;

interface RecommendationCard {
  id: number;
  course_name: string;
  time_slot: string;
  reason: string;
  difficulty: string;
}

interface AiResponse {
  response?: string | null;
  display_query?: string;
  source?: Source;
  query_id?: number | null;
  error?: string | null;
  hallucination_warning?: boolean;
  taboo_filtered?: boolean;
  recommendation_cards?: RecommendationCard[];
  active_student_name?: string | null;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  source?: Source;
  queryId?: number | null;
  warning?: boolean;
  filtered?: boolean;
  cards?: RecommendationCard[];
}

interface FlagRow {
  id: number;
  flagged_by_name: string;
  query_owner_name: string;
  reason: string;
  query_text: string;
  response_text: string;
  source: string;
  status: string;
}

const tabooWords = [
  'stupid', 'idiot', 'dumb', 'moron', 'hate',
  'worthless', 'incompetent', 'cheat', 'cheater',
  'plagiarize', 'plagiarism', 'expel', 'expelled',
  'loser', 'failure', 'fuck', 'fucking', 'fucked',
  'fucker', 'shit', 'shitty', 'bullshit', 'bitch',
  'bitches', 'asshole', 'dick', 'dicks', 'crap',
  'damn', 'bastard', 'slut', 'whore', 'piss',
  'suck', 'sucks', 'sucked', 'sucking',
];

function filterTaboo(value: string): string {
  let filtered = value;
  for (const word of tabooWords) {
    filtered = filtered.replace(new RegExp(`\\b${escapeRegExp(word)}\\b`, 'gi'), '****');
  }
  return filtered;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function AIAssistant(): React.ReactElement {
  const data = getPageData() as any;
  const role = data.role || 'visitor';
  const username = data.username || 'Guest';
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeStudentName, setActiveStudentName] = useState<string | null>(data.active_student_name || null);
  const [flagsOpen, setFlagsOpen] = useState(false);
  const [flags, setFlags] = useState<FlagRow[]>([]);
  const [flagLoading, setFlagLoading] = useState(false);
  const threadRef = useRef<HTMLDivElement | null>(null);

  const quickActions = useMemo(() => {
    if (role === 'student') {
      return ['What is my GPA?', 'What classes am I taking?', 'What classes should I take?'];
    }
    if (role === 'registrar') {
      return ['List every student with GPA and classes', 'What classes is demo_student1 enrolled in?', 'What else can I register them for?'];
    }
    if (role === 'instructor') {
      return ['Summarize my assigned courses', 'Who is enrolled in my classes?', 'What courses are available?'];
    }
    return ['What courses are available?', 'What program requirements are public?', 'What classes can visitors see?'];
  }, [role]);

  async function submitQuery(rawText: string): Promise<void> {
    const text = rawText.trim();
    if (!text || loading) return;
    setInput('');
    setLoading(true);

    const userMessageId = crypto.randomUUID();
    setMessages(prev => [...prev, {
      id: userMessageId,
      role: 'user',
      text: filterTaboo(text),
      filtered: filterTaboo(text) !== text,
    }]);

    try {
      const response = await fetch('/api/ai/assistant', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({ query_text: text }),
      });
      const payload = (await response.json()) as AiResponse;

      setMessages(prev => prev.map(msg => (
        msg.id === userMessageId && payload.display_query
          ? { ...msg, text: payload.display_query, filtered: payload.display_query !== text }
          : msg
      )));

      if (payload.active_student_name !== undefined) {
        setActiveStudentName(payload.active_student_name || null);
      }

      setMessages(prev => [...prev, {
        id: crypto.randomUUID(),
        role: 'assistant',
        text: payload.error || payload.response || 'No response returned.',
        source: payload.source || (payload.error ? 'local_error' : null),
        queryId: payload.query_id,
        warning: Boolean(payload.hallucination_warning),
        filtered: Boolean(payload.taboo_filtered),
        cards: payload.recommendation_cards || [],
      }]);
    } catch (error) {
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(),
        role: 'assistant',
        text: (error as Error).message || 'The request could not be completed.',
        source: 'local_error',
      }]);
    } finally {
      setLoading(false);
      window.setTimeout(() => threadRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }), 20);
    }
  }

  async function enroll(courseId: number): Promise<string> {
    const response = await fetch(`/api/ai/enroll/${courseId}`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    });
    const payload = await response.json();
    if (!payload.ok) throw new Error(payload.message || payload.error || 'Could not enroll.');
    return payload.message || 'Enrolled.';
  }

  async function flag(queryId: number): Promise<void> {
    const reason = window.prompt('Why are you flagging this response?', 'Inaccurate or inappropriate response');
    if (!reason) return;
    await fetch(`/api/ai/query/${queryId}/flag`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ reason }),
    });
  }

  async function loadFlags(): Promise<void> {
    setFlagsOpen(open => !open);
    if (flags.length > 0 || flagLoading) return;
    setFlagLoading(true);
    try {
      const response = await fetch('/api/ai/flags?status=pending', { credentials: 'same-origin' });
      const payload = await response.json();
      if (payload.ok) setFlags(payload.flags || []);
    } finally {
      setFlagLoading(false);
    }
  }

  return (
    <PageLayout username={username} role={role} activePage="ai_assistant">
      <div style={styles.shell}>
        <div style={styles.header}>
          <div>
            <h2 style={styles.title}>College0 Assistant</h2>
            <p style={styles.subtle}>Ask about courses, grades, recommendations, and academic records.</p>
            {role === 'registrar' && activeStudentName && (
              <div style={styles.contextPill}>Active student: {activeStudentName}</div>
            )}
          </div>
          {role === 'registrar' && (
            <button type="button" style={styles.secondaryButton} onClick={loadFlags}>
              Review Flagged Responses {data.pending_flags_count ? `(${data.pending_flags_count})` : ''}
            </button>
          )}
        </div>

        {flagsOpen && (
          <section style={styles.flagsPanel}>
            <h3 style={styles.panelTitle}>Pending Flags</h3>
            {flagLoading && <p style={styles.subtle}>Loading flags...</p>}
            {!flagLoading && flags.length === 0 && <p style={styles.subtle}>No pending flagged responses.</p>}
            {flags.map(row => (
              <article key={row.id} style={styles.flagCard}>
                <div style={styles.flagMeta}>Flagged by {row.flagged_by_name} · Original user {row.query_owner_name} · {row.source}</div>
                <strong>Reason</strong>
                <p>{row.reason}</p>
                <strong>Original Query</strong>
                <p>{row.query_text}</p>
                <strong>AI Response</strong>
                <p>{row.response_text}</p>
              </article>
            ))}
          </section>
        )}

        <section style={styles.chatPanel}>
          {messages.length === 0 ? (
            <div style={styles.emptyState}>
              <h1 style={styles.heroTitle}>How can I help?</h1>
              <p style={styles.subtle}>Try one of the quick actions or type your own question.</p>
            </div>
          ) : (
            <div style={styles.thread}>
              {messages.map(message => (
                <ChatMessage key={message.id} message={message} onEnroll={enroll} onFlag={flag} />
              ))}
              {loading && (
                <div style={styles.aiRow}>
                  <div style={styles.avatar}>C0</div>
                  <div style={styles.dots}><span /> <span /> <span /></div>
                </div>
              )}
              <div ref={threadRef} />
            </div>
          )}
        </section>

        <div style={styles.quickActions}>
          {quickActions.map(action => (
            <button key={action} type="button" style={styles.quickButton} onClick={() => submitQuery(action)}>
              {action}
            </button>
          ))}
        </div>

        <form
          style={styles.composer}
          onSubmit={event => {
            event.preventDefault();
            void submitQuery(input);
          }}
        >
          <textarea
            value={input}
            onChange={event => setInput(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                void submitQuery(input);
              }
            }}
            placeholder="Message College0 Assistant"
            rows={1}
            style={styles.textarea}
          />
          <button type="submit" disabled={loading || input.trim().length === 0} style={styles.sendButton}>↑</button>
        </form>
        <div style={styles.disclaimer}>AI is a tool and can make mistakes.</div>
      </div>
    </PageLayout>
  );
}

function ChatMessage({
  message,
  onEnroll,
  onFlag,
}: {
  message: Message;
  onEnroll: (courseId: number) => Promise<string>;
  onFlag: (queryId: number) => Promise<void>;
}) {
  if (message.role === 'user') {
    return (
      <div style={styles.userRow}>
        <div>
          <div style={styles.userBubble}>{message.text}</div>
          {message.filtered && <div style={styles.filterNote}>Taboo language filtered</div>}
        </div>
      </div>
    );
  }

  return (
    <div style={styles.aiRow}>
      <div style={styles.avatar}>C0</div>
      <div style={styles.aiBody}>
        <div style={{ whiteSpace: 'pre-wrap' }}>{message.text}</div>
        {message.warning && <div style={styles.warning}>This answer was generated by an AI model. Verify important information.</div>}
        {message.filtered && <div style={styles.filtered}>Some language was filtered by the College0 taboo-word system.</div>}
        {message.cards && message.cards.length > 0 && <RecommendationStrip cards={message.cards} onEnroll={onEnroll} />}
        <div style={styles.sourceLine}>
          <span style={message.filtered ? styles.filteredBadge : message.source === 'llm' ? styles.llmBadge : styles.localBadge}>
            {message.filtered ? 'Filtered' : message.source === 'llm' ? 'LLM' : message.source === 'local_error' ? 'Error' : 'Local DB'}
          </span>
        </div>
        {message.queryId && (
          <div style={styles.feedback}>
            <span>Was this helpful?</span>
            <button type="button" style={styles.miniButton}>Yes</button>
            <button type="button" style={styles.miniButton}>No</button>
            <button type="button" style={styles.miniButton} onClick={() => void onFlag(message.queryId!)}>Flag response</button>
          </div>
        )}
      </div>
    </div>
  );
}

function RecommendationStrip({
  cards,
  onEnroll,
}: {
  cards: RecommendationCard[];
  onEnroll: (courseId: number) => Promise<string>;
}) {
  const [status, setStatus] = useState<Record<number, string>>({});
  return (
    <div style={styles.recStrip}>
      {cards.map(card => (
        <article key={card.id} style={styles.recCard}>
          <div style={styles.recName}>{card.course_name}</div>
          <span style={styles.diffBadge}>{card.difficulty}</span>
          <p style={styles.recReason}>{card.reason}</p>
          <div style={styles.recSlot}>{card.time_slot}</div>
          <button
            type="button"
            style={styles.enrollButton}
            disabled={status[card.id] === 'Enrolled'}
            onClick={async () => {
              setStatus(prev => ({ ...prev, [card.id]: 'Enrolling...' }));
              try {
                await onEnroll(card.id);
                setStatus(prev => ({ ...prev, [card.id]: 'Enrolled' }));
              } catch (error) {
                setStatus(prev => ({ ...prev, [card.id]: (error as Error).message }));
              }
            }}
          >
            {status[card.id] || 'Enroll'}
          </button>
        </article>
      ))}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  shell: { maxWidth: 840, margin: '0 auto', minHeight: 'calc(100vh - 4rem)' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, marginBottom: 20 },
  title: { margin: '0 0 4px', color: '#223f66', fontSize: 28 },
  subtle: { color: '#6b7280', margin: 0 },
  contextPill: { display: 'inline-flex', marginTop: 12, borderRadius: 999, background: '#eaf1ff', color: '#223f66', padding: '7px 12px', fontSize: 13, fontWeight: 700 },
  secondaryButton: { border: '1px solid #d8dee8', background: 'white', color: '#223f66', borderRadius: 999, padding: '9px 13px', fontWeight: 700, cursor: 'pointer' },
  flagsPanel: { background: 'white', border: '1px solid #e5e7eb', borderRadius: 16, padding: 16, marginBottom: 18 },
  panelTitle: { margin: '0 0 12px', color: '#223f66' },
  flagCard: { borderTop: '1px solid #e5e7eb', paddingTop: 12, marginTop: 12 },
  flagMeta: { color: '#6b7280', fontSize: 12, marginBottom: 8 },
  chatPanel: { minHeight: 440, background: '#f7f8fb', borderRadius: 18, padding: '24px 0' },
  emptyState: { minHeight: 360, display: 'flex', flexDirection: 'column', justifyContent: 'center' },
  heroTitle: { color: '#223f66', fontSize: 44, margin: '0 0 10px' },
  thread: { display: 'flex', flexDirection: 'column', gap: 28 },
  userRow: { display: 'flex', justifyContent: 'flex-end' },
  userBubble: { maxWidth: 620, background: '#eef2f7', borderRadius: 22, padding: '13px 17px', lineHeight: 1.55, whiteSpace: 'pre-wrap' },
  filterNote: { marginTop: 6, textAlign: 'right', color: '#b42318', fontSize: 12 },
  aiRow: { display: 'grid', gridTemplateColumns: '32px 1fr', gap: 14, alignItems: 'start' },
  avatar: { width: 32, height: 32, borderRadius: '50%', background: '#223f66', color: 'white', display: 'grid', placeItems: 'center', fontSize: 13, fontWeight: 800 },
  aiBody: { lineHeight: 1.65, minWidth: 0 },
  warning: { marginTop: 10, color: '#8a6400', background: '#fff7df', border: '1px solid #f4d987', borderRadius: 10, padding: '9px 12px', fontSize: 13 },
  filtered: { marginTop: 10, color: '#b42318', background: '#feeceb', border: '1px solid #fecaca', borderRadius: 10, padding: '9px 12px', fontSize: 13 },
  sourceLine: { marginTop: 12, display: 'flex', gap: 8 },
  localBadge: { borderRadius: 999, padding: '4px 10px', fontSize: 12, fontWeight: 700, background: '#e8f7ee', color: '#167a3d' },
  llmBadge: { borderRadius: 999, padding: '4px 10px', fontSize: 12, fontWeight: 700, background: '#fff7df', color: '#8a6400' },
  filteredBadge: { borderRadius: 999, padding: '4px 10px', fontSize: 12, fontWeight: 700, background: '#feeceb', color: '#b42318' },
  feedback: { marginTop: 14, display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center', color: '#6b7280', fontSize: 13 },
  miniButton: { border: '1px solid #e5e7eb', background: 'white', color: '#1f2937', borderRadius: 999, padding: '6px 11px', cursor: 'pointer' },
  recStrip: { display: 'flex', gap: 12, overflowX: 'auto', padding: '12px 2px 6px', marginTop: 10, maxWidth: 'min(720px, calc(100vw - 360px))' },
  recCard: { flex: '0 0 230px', background: 'white', border: '1px solid #e5e7eb', borderRadius: 16, padding: 14, boxShadow: '0 8px 22px rgba(15,23,42,.06)' },
  recName: { fontWeight: 800, color: '#223f66', marginBottom: 8 },
  diffBadge: { display: 'inline-block', borderRadius: 999, padding: '3px 9px', fontSize: 12, fontWeight: 700, background: '#eaf1ff', color: '#315b92', marginBottom: 9 },
  recReason: { color: '#6b7280', fontSize: 13, lineHeight: 1.4, minHeight: 54 },
  recSlot: { color: '#8b94a3', fontSize: 12, margin: '10px 0' },
  enrollButton: { width: '100%', border: 0, borderRadius: 10, background: '#223f66', color: 'white', padding: '9px 10px', fontWeight: 800, cursor: 'pointer' },
  quickActions: { display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 8, marginTop: 8 },
  quickButton: { flex: '0 0 auto', border: '1px solid #d8dee8', background: 'white', color: '#223f66', borderRadius: 999, padding: '9px 13px', fontWeight: 700, cursor: 'pointer' },
  composer: { display: 'flex', alignItems: 'flex-end', gap: 10, background: 'white', border: '1px solid #d8dee8', borderRadius: 24, padding: '10px 10px 10px 18px', boxShadow: '0 14px 42px rgba(15,23,42,.12)' },
  textarea: { flex: 1, border: 0, outline: 0, resize: 'none', minHeight: 28, padding: '9px 0', font: 'inherit', lineHeight: 1.45, background: 'transparent' },
  sendButton: { width: 42, height: 42, border: 0, borderRadius: '50%', background: '#223f66', color: 'white', cursor: 'pointer', fontSize: 18 },
  disclaimer: { marginTop: 8, color: '#8b94a3', fontSize: 12, textAlign: 'center' },
  dots: { color: '#223f66', padding: '10px 0', fontWeight: 800 },
};
