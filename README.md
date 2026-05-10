# Multi-Agent Research Assistant

An agentic research application that turns a user question into a structured report using a LangGraph multi-agent workflow. The system searches the web, summarizes evidence, checks confidence, retries when needed, and serves the final report through a public Streamlit interface backed by AWS Lambda.

![Architecture](./images/collaborative%20_multi_agent_ai_system_with_langgraph.png)

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture Overview](#architecture-overview)
  - [1. Serving Flow](#1-serving-flow)
  - [2. Multi-Agent Workflow](#2-multi-agent-workflow)
  - [3. Rate Limiting](#3-rate-limiting)
  - [4. Deployment Pipeline](#4-deployment-pipeline)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Setup](#setup)
  - [Environment Variables](#environment-variables)
  - [Install Dependencies](#install-dependencies)
  - [Run Streamlit Locally](#run-streamlit-locally)
- [AWS Deployment](#aws-deployment)
  - [DynamoDB Rate Limit Table](#dynamodb-rate-limit-table)
  - [Lambda Deployment](#lambda-deployment)
  - [GitHub Actions Deployment](#github-actions-deployment)
- [Streamlit Cloud Deployment](#streamlit-cloud-deployment)
- [Runtime Configuration](#runtime-configuration)

## Project Overview

This project is a deployable multi-agent AI system built around a production-style request flow:

1. A user submits a research question in Streamlit.
2. Streamlit invokes an AWS Lambda function.
3. Lambda checks DynamoDB-backed request limits.
4. The LangGraph workflow coordinates specialized agents.
5. The final structured report is returned to the Streamlit UI.

The project demonstrates how a multi-agent research workflow can be packaged, deployed, rate-limited, and made available publicly with cost controls.

## Architecture Overview

The system is organized into four main layers: **serving**, **agent orchestration**, **rate limiting**, and **deployment**.

### 1. Serving Flow

- **User** interacts with the public Streamlit application.
- **Streamlit Cloud** hosts the frontend and stores backend invocation credentials in private app secrets.
- **AWS Lambda** runs the backend workflow as a Docker container.
- **Amazon ECR** stores the Lambda-compatible Docker image.
- **CloudWatch Logs** captures runtime logs for debugging and observability.

Active request path:

```text
User -> Streamlit Cloud -> AWS Lambda -> DynamoDB rate limit check -> LangGraph -> Streamlit
```

### 2. Multi-Agent Workflow

The LangGraph workflow coordinates specialized agents as a graph instead of a single prompt chain.

- **Search Agent** retrieves web evidence using Serper.
- **Summarization Agent** condenses retrieved content.
- **Fact-Checking Agent** validates confidence against the research question.
- **Report Agent** generates the final structured report.
- **Retry Routing** sends the workflow back for more evidence when confidence is too low.

Each agent owns a focused responsibility, while LangGraph controls state transitions, routing, and retry behavior across the workflow.

### 3. Rate Limiting

The public demo is rate-limited inside Lambda before the research workflow starts.

Current intended limit:

- 2 requests per Streamlit browser session per month

### 4. Deployment Pipeline

GitHub Actions handles the production deployment flow:

```text
Push to GitHub -> Build Docker image -> Push to ECR -> Update Lambda image -> Update Lambda env vars
```

The deployment script also ensures the Lambda execution role has the DynamoDB permission required for rate limiting.

## Features

- Streamlit UI
- Serverless backend on AWS Lambda
- Dockerized Lambda runtime
- LangGraph-based agent orchestration
- Web search with Serper
- OpenRouter model integration
- Confidence-based retry loop
- DynamoDB-backed public demo rate limiting
- CloudWatch runtime logging
- GitHub Actions deployment to AWS

## Technology Stack

| Layer | Technology |
| --- | --- |
| Frontend | Streamlit |
| Agent Orchestration | LangGraph |
| LLM Provider | OpenRouter |
| Web Search | Serper API |
| Backend Runtime | AWS Lambda |
| Container Registry | Amazon ECR |
| Rate Limiting | Amazon DynamoDB |
| Logs | Amazon CloudWatch |
| CI/CD | GitHub Actions |
| Package Management | uv |
| Language | Python 3.12 |

## Setup

### Environment Variables

Create a local `.env` file from the example:

```bash
cp env.example .env
```

Required application variables:

- `SERPER_API_KEY`
- `OPENROUTER_API_KEY`
- `OPENROUTER_BASE_URL`

Required AWS deployment variables:

- `AWS_REGION`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_ACCOUNT_ID`
- `REPOSITORY_NAME`
- `IMAGE_NAME`
- `LAMBDA_FUNCTION_NAME`
- `ROLE_NAME`

Required rate-limit variables:

- `RATE_LIMIT_ENABLED`
- `RATE_LIMIT_TABLE_NAME`
- `RATE_LIMIT_MONTHLY_LIMIT`
- `RATE_LIMIT_PER_CLIENT_LIMIT`

### Install Dependencies

```bash
uv sync --all-extras
```

### Run Streamlit Locally

```bash
uv run streamlit run streamlit_app.py
```

For local Streamlit testing, configure AWS region, AWS credentials, and the Lambda function name in your local environment.

## AWS Deployment

### DynamoDB Rate Limit Table

Create the DynamoDB table:

```bash
aws dynamodb create-table \
  --table-name <RATE_LIMIT_TABLE_NAME> \
  --attribute-definitions AttributeName=pk,AttributeType=S \
  --key-schema AttributeName=pk,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region <AWS_REGION>
```

Enable TTL on the `ttl` attribute:

```bash
aws dynamodb update-time-to-live \
  --table-name <RATE_LIMIT_TABLE_NAME> \
  --time-to-live-specification "Enabled=true,AttributeName=ttl" \
  --region <AWS_REGION>
```

The Lambda execution role needs:

```json
{
  "Effect": "Allow",
  "Action": "dynamodb:UpdateItem",
  "Resource": "arn:aws:dynamodb:<AWS_REGION>:<AWS_ACCOUNT_ID>:table/<RATE_LIMIT_TABLE_NAME>"
}
```

### Lambda Deployment

Build and deploy manually:

```bash
chmod +x build_deploy.sh
./build_deploy.sh
```

The script:

- syncs dependencies with `uv`
- runs Ruff
- builds a Lambda-compatible Docker image
- pushes the image to ECR
- creates or updates the Lambda function
- sets Lambda runtime environment variables
- adds the DynamoDB rate-limit policy to the Lambda role

### GitHub Actions Deployment

The workflow lives at:

```text
.github/workflows/deploy.yml
```

Deployment runs on:

```text
ubuntu-22.04
```

Add the application, AWS deployment, and rate-limit variables as GitHub repository secrets before running the workflow.

After that, a normal push can redeploy the backend:

```bash
git add .
git commit -m "Update application"
git push
```

## Streamlit Cloud Deployment

1. Deploy the repository on Streamlit Community Cloud.
2. Set the main file path:

   ```text
   streamlit_app.py
   ```

3. Add the AWS region, limited Lambda invoke credentials, and Lambda function name in Streamlit secrets.

The Streamlit IAM user should only have permission to invoke this Lambda function:

```json
{
  "Effect": "Allow",
  "Action": "lambda:InvokeFunction",
  "Resource": "arn:aws:lambda:<AWS_REGION>:<AWS_ACCOUNT_ID>:function:<LAMBDA_FUNCTION_NAME>"
}
```

## Runtime Configuration

The workflow parameters can be adjusted from the Streamlit UI:

| Parameter | Purpose |
| --- | --- |
| Confidence threshold | Minimum confidence required before accepting the fact-check result |
| Max retries | Number of additional search attempts if confidence is too low |
| Extra results per retry | Additional search results added during retry |

Model configuration is managed in `config/settings.py`.
