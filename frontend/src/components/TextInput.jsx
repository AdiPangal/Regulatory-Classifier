import { useState } from 'react';
import '../styles/input.css';

const TextInput = ({ onTextSubmit, placeholder = 'Enter text to classify...' }) => {
  const [text, setText] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (text.trim()) {
      onTextSubmit(text.trim());
    }
  };

  return (
    <div className="text-input-container">
      <form onSubmit={handleSubmit}>
        <textarea
          className="text-input-area"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={placeholder}
          rows={12}
        />
        <button type="submit" className="submit-button" disabled={!text.trim()}>
          Classify Text
        </button>
      </form>
    </div>
  );
};

export default TextInput;

