import React from 'react';
import { getPageData } from '../lib/data';
import { PageLayout } from '../components/Sidebar';
 
export function Reviews(): React.ReactElement {
  const data = getPageData() as any;
  const username = data.username || '—';
  const role = data.role || 'student';
  const reviews = data.reviews || [];
  const courseId = data.course_id;
  const message = data.message;
 
  return (
    <PageLayout username={username} role={role} activePage="reviews">
      <h2 style={{ marginBottom: '1.5rem' }}>Course Reviews</h2>
      {message && <div className={message.toLowerCase().includes('not') || message.toLowerCase().includes('warning') ? 'error' : 'info'} style={{ marginBottom: '1rem' }}>{message}</div>}
      {role === 'student' && (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <h3 style={{ marginBottom: '1rem' }}>Submit a Review</h3>
          <form method="POST" action={`/reviews/submit/${courseId}`}>
            <label>Star Rating</label>
            <select name="star_rating">
              <option value="5">⭐⭐⭐⭐⭐ (5 - Excellent)</option>
              <option value="4">⭐⭐⭐⭐ (4 - Good)</option>
              <option value="3">⭐⭐⭐ (3 - Average)</option>
              <option value="2">⭐⭐ (2 - Poor)</option>
              <option value="1">⭐ (1 - Terrible)</option>
            </select>
            <label>Your Review</label>
            <textarea name="review_text" rows={4} placeholder="Write your review here..." />
            <button type="submit" className="block">Submit Review</button>
          </form>
        </div>
      )}
      <div className="card">
        <h3 style={{ marginBottom: '1rem' }}>All Reviews</h3>
        {reviews.length > 0 ? reviews.map((r: any, i: number) => (
          <div key={i} style={{ borderLeft: `4px solid ${r.is_visible === 0 ? '#dc2626' : '#2E4A7A'}`, padding: '1rem 1.25rem', marginBottom: '1rem', background: r.is_visible === 0 ? '#fff5f5' : '#f9f9f9', borderRadius: 6 }}>
            {role === 'registrar' && r.is_visible === 0 && (
              <span style={{ fontSize: 11, fontWeight: 700, background: '#dc2626', color: 'white', padding: '2px 8px', borderRadius: 20, marginBottom: 8, display: 'inline-block' }}>🚫 HIDDEN — 3+ taboo words</span>
            )}
            <div style={{ color: '#f5a623', fontSize: '1.1rem', marginBottom: '.4rem' }}>{'⭐'.repeat(r.star_rating)} <span className="muted">({r.star_rating}/5)</span></div>
            <p style={{ marginBottom: '.4rem' }}>{role === 'registrar' ? (r.review_text || r.filtered_text) : r.review_text}</p>
            {role === 'registrar' ? <p className="muted">Reviewer: <strong>{r.reviewer_name}</strong></p> : <p className="muted" style={{ fontStyle: 'italic' }}>Anonymous Student</p>}
          </div>
        )) : <p className="muted">No reviews yet for this course.</p>}
      </div>
    </PageLayout>
  );
}