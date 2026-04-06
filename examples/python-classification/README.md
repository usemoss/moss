# Moss Python Classification Examples

Demonstrates the Moss Classification SDK for question detection and normalization.

## Prerequisites

1. **Create a Moss account** at [moss.dev](https://moss.dev) (free tier available).
2. **Create a project** from the dashboard — this gives you a **Project ID** and **Project Key**.

## Setup

1. **Set up Python environment:**
   - Ensure you have Python 3.9+ installed
   - Create a virtual environment (recommended):

     ```bash
     python3 -m venv venv
     source venv/bin/activate  # On Windows: venv\Scripts\activate
     ```

2. **Install dependencies:**

   ```bash
   python3 -m pip install -r requirements.txt
   ```

3. **Configure credentials:**
   - Copy `.env.template` to `.env`
   - Fill in your project credentials from the Moss dashboard:

     ```bash
     MOSS_PROJECT_ID=your_actual_project_id
     MOSS_PROJECT_KEY=your_actual_project_key
     ```

## Running Samples

### Classification Sample

Classifies utterances as questions or statements, then demonstrates question normalization with conversation context:

```bash
python classify_sample.py
```

**What it does:**

1. **Question Detection** — sends plain utterances and classifies each as `question` or `statement` with a confidence score.
2. **Question Normalization** — sends noisy ASR utterances with conversation context. Questions are rewritten into clean standalone form (e.g. `"you use aws right?"` becomes `"Do you use AWS?"`).

## Requirements

- Python 3.9+
- Valid Moss project credentials
