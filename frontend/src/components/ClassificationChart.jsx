import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import '../styles/dashboard.css';

const ClassificationChart = ({ data }) => {
  const colors = {
    'Public': '#10b981',
    'Confidential': '#f59e0b',
    'Highly Sensitive': '#ef4444'
    // Note: "Unsafe" is a safety flag, not a classification category
  };

  const chartData = Object.entries(data.distribution || {}).map(([name, value]) => ({
    name,
    value
  }));

  return (
    <div className="chart-container">
      <h3 className="chart-title">Classification Distribution</h3>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
            outerRadius={80}
            fill="#8884d8"
            dataKey="value"
          >
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={colors[entry.name] || '#8884d8'} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
      <div className="chart-summary">
        <p>Total Classifications: {data.total || 0}</p>
      </div>
    </div>
  );
};

export default ClassificationChart;

