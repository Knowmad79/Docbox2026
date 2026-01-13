import React from "react";

interface EmailDetailProps {
  subject: string;
  from: string;
  date: string;
  html: string;
  onClose: () => void;
}

const EmailDetail: React.FC<EmailDetailProps> = ({ subject, from, date, html, onClose }) => {
  return (
    <div className="email-detail-modal">
      <button className="close-btn" onClick={onClose}>&times;</button>
      <h2>{subject}</h2>
      <div className="email-meta">
        <span><strong>From:</strong> {from}</span>
        <span><strong>Date:</strong> {date}</span>
      </div>
      <div className="email-html-body" style={{ border: '1px solid #eee', padding: 16, background: '#fff', borderRadius: 8, marginTop: 16 }}>
        {/* Render HTML safely */}
        <iframe
          title="Email HTML"
          srcDoc={html}
          style={{ width: '100%', minHeight: 400, border: 'none' }}
        />
      </div>
    </div>
  );
};

export default EmailDetail;
