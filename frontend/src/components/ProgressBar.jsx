import '../styles/loading.css';

const ProgressBar = ({ progress = 0, total = 0, completed = 0 }) => {
  const percentage = total > 0 ? (completed / total) * 100 : 0;
  
  return (
    <div className="progress-container">
      <div className="progress-bar">
        <div 
          className="progress-fill" 
          style={{ width: `${percentage}%` }}
        ></div>
      </div>
      <p className="progress-text">
        {completed} of {total} documents processed
      </p>
    </div>
  );
};

export default ProgressBar;

