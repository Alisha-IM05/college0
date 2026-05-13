import React from 'react';
import { getPageData } from '../lib/data';
import { Navbar } from '../components/Navbar';

export function Reviews(): React.ReactElement {
  const data = getPageData() as any;
  const username = data.username || '—';
  const role = data.role || 'student';
  const reviews = data.reviews || [];
  const courseId = data.course_id;
  const message = data.message;

  return (
    <>
      <Navbar username={username} />
      <div className="container">
        <h2>Course Reviews</h2>

        {message && (
          <div className={message.toLowerCase().includes('not') || message.toLowerCase().includes('warning') ? 'error' : 'info'}>
            {message}
          </div>
        )}

        {role === 'student' && (
          <div className="card">
            <h3>Submit a Review</h3>
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
              <textarea
                name="review_text"
                rows={4}
                placeholder="Write your review here..."
                style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '5px', fontSize: '14px', fontFamily: 'inherit' }}
              />
              <button type="submit" className="block">Submit Review</button>
            </form>
          </div>
        )}

        <div className="card">
          <h3>All Reviews</h3>
          {reviews.length > 0 ? reviews.map((r: any, i: number) => (
            <div key={i} style={{ borderLeft: '4px solid #2E4A7A', padding: '1rem', marginBottom: '1rem', background: '#f9f9f9', borderRadius: '6px' }}>
              <div style={{ color: '#f5a623', fontSize: '1.1rem', marginBottom: '.4rem' }}>
                {'⭐'.repeat(r.star_rating)}
                <span className="muted" style={{ marginLeft: '.5rem' }}>({r.star_rating}/5)</span>
              </div>
              <p style={{ marginBottom: '.4rem' }}>{r.review_text}</p>
              {role === 'registrar'
                ? <p className="muted">Reviewer: <strong>{r.reviewer_name}</strong></p>
                : <p className="muted" style={{ fontStyle: 'italic' }}>Anonymous Student</p>
              }
            </div>
          )) : (
            <p className="muted">No reviews yet for this course.</p>
          )}
        </div>
      </div>
    </>
  );
}