# Regulatory Classifier Frontend

React frontend application for the Regulatory Document Classifier.

## Setup

1. Install dependencies:
```bash
npm install
```

2. Create a `.env` file in the `frontend/` directory:
```bash
VITE_API_BASE_URL=http://localhost:8000
```

3. Start the development server:
```bash
npm run dev
```

The app will be available at `http://localhost:5173` (or the port Vite assigns).

## Features

- **Input Page**: Upload PDF/image files or enter text directly
- **Loading Page**: Shows processing status
- **Results Page**: Displays classification results with citations and reasoning

## Environment Variables

- `VITE_API_BASE_URL`: Backend API base URL (default: `http://localhost:8000`)

## Build for Production

```bash
npm run build
```

The built files will be in the `dist/` directory.
