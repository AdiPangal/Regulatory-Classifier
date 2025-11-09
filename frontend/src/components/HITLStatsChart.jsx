import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import '../styles/dashboard.css';

const HITLStatsChart = ({ data }) => {
  // Transform HITL stats data for chart
  const chartData = [];
  
  if (data && data.accuracy_by_classification) {
    Object.entries(data.accuracy_by_classification).forEach(([classification, accuracy]) => {
      chartData.push({
        classification,
        accuracy: (accuracy * 100).toFixed(1)
      });
    });
  }

  if (chartData.length === 0) {
    return (
      <div className="chart-container">
        <h3 className="chart-title">HITL Feedback Statistics</h3>
        <p className="no-data">No feedback data available yet.</p>
      </div>
    );
  }

  return (
    <div className="chart-container">
      <h3 className="chart-title">HITL Feedback Statistics</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="classification" />
          <YAxis label={{ value: 'Accuracy (%)', angle: -90, position: 'insideLeft' }} />
          <Tooltip />
          <Legend />
          <Bar dataKey="accuracy" fill="#3b82f6" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default HITLStatsChart;

