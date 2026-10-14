"""OpenAI function-calling tool schemas for the fraud detection agent."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_transactions",
            "description": "Search and filter transactions. Returns matching transactions with key fields including merchant_name, user_id, amount, location, and fraud status. Use for looking up a specific transaction by ID (pass transaction_id), finding user history, or filtering by criteria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {
                        "type": "integer",
                        "description": "Look up a single transaction by its ID. Returns merchant_name, user_id, amount, location, and is_fraud."
                    },
                    "user_id": {
                        "type": "integer",
                        "description": "Filter by user ID"
                    },
                    "merchant_name": {
                        "type": "string",
                        "description": "Filter by merchant name (partial match)"
                    },
                    "merchant_state": {
                        "type": "string",
                        "description": "Filter by merchant state/region code"
                    },
                    "merchant_country": {
                        "type": "string",
                        "description": "Filter by merchant country (2-letter code, e.g. US, GB, DE, JP, CN, BR, RU)"
                    },
                    "min_amount": {
                        "type": "number",
                        "description": "Minimum transaction amount"
                    },
                    "max_amount": {
                        "type": "number",
                        "description": "Maximum transaction amount"
                    },
                    "is_fraud": {
                        "type": "boolean",
                        "description": "Filter by fraud status. Set to true when the user asks about fraud or fraudulent transactions. Set to false to see only legitimate transactions."
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date filter (YYYY-MM-DD)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date filter (YYYY-MM-DD)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (default 20)"
                    },
                    "order_by": {
                        "type": "string",
                        "enum": ["amount_desc", "amount_asc", "date_desc", "date_asc", "fraud_score_desc"],
                        "description": "Sort order for results"
                    }
                },
                "required": [],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "score_transaction",
            "description": "Score a transaction for fraud using the XGBoost model. Can score by transaction ID (from database) or with raw transaction data. Returns fraud probability and risk level.",
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {
                        "type": "integer",
                        "description": "Score an existing transaction by its ID"
                    },
                    "transaction_data": {
                        "type": "object",
                        "description": "Raw transaction fields for scoring a new transaction",
                        "properties": {
                            "amount": {"type": "number"},
                            "hour": {"type": "integer"},
                            "merchant_state": {"type": "string"},
                            "merchant_country": {"type": "string"},
                            "mcc": {"type": "integer"},
                            "use_chip": {"type": "string"},
                        }
                    },
                    "explain": {
                        "type": "boolean",
                        "description": "Include SHAP explanation (default true)"
                    }
                },
                "required": [],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "explain_prediction",
            "description": "Get a detailed SHAP explanation for a transaction's fraud prediction. Shows the top features that influenced the score and their contributions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {
                        "type": "integer",
                        "description": "Transaction ID to explain"
                    }
                },
                "required": ["transaction_id"],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_risk_dashboard",
            "description": "Get aggregate fraud analytics and KPIs. Returns summary statistics including total transactions, fraud rate, fraud by country, fraud by state/region, fraud by merchant category (MCC), hourly fraud patterns, and top fraud amounts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "time_period": {
                        "type": "string",
                        "enum": ["all", "2018", "2019", "2020"],
                        "description": "Time period filter"
                    },
                    "group_by": {
                        "type": "string",
                        "enum": ["country", "state", "mcc", "hour", "merchant", "user"],
                        "description": "Dimension to aggregate by (country for international view)"
                    }
                },
                "required": [],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "detect_alert_patterns",
            "description": "Detect specific fraud patterns for a user or merchant. Identifies velocity attacks (rapid transactions), geographic anomalies (out-of-state), amount spikes (unusual amounts), and late-night activity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "User ID to analyze"
                    },
                    "merchant_name": {
                        "type": "string",
                        "description": "Merchant name to analyze"
                    },
                    "pattern_type": {
                        "type": "string",
                        "enum": ["velocity", "geo_anomaly", "amount_spike", "late_night", "all"],
                        "description": "Type of pattern to detect (default: all)"
                    }
                },
                "required": [],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_threshold",
            "description": "Sweep the XGBoost decision threshold across 0.05-0.95 and compute precision, recall, F1, and confusion-matrix counts at each cutoff. Use when the user asks about threshold tuning, precision/recall tradeoffs, how many alerts would fire at a given threshold, or what score boundary best separates fraud from legitimate.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sample_size": {
                        "type": "integer",
                        "description": "Balanced sample of transactions to evaluate (default 5000, max 10000)"
                    }
                },
                "required": [],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "monitor_drift",
            "description": "Compare feature distributions and model performance between a reference year and a current year using PSI (Population Stability Index). Use when the user asks about model drift, whether the model is still accurate, performance over time, or feature distribution changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reference_year": {
                        "type": "integer",
                        "description": "Baseline year (default 2018)"
                    },
                    "current_year": {
                        "type": "integer",
                        "description": "Year to compare against the baseline (default 2020)"
                    },
                    "report_type": {
                        "type": "string",
                        "enum": ["feature_drift", "performance_over_time", "score_distribution"],
                        "description": "What to report: PSI on features, yearly metrics, or score histograms. Default: feature_drift."
                    }
                },
                "required": [],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "investigate_merchant",
            "description": "Build a full investigation report on a single merchant: KPIs, geographic spread, monthly trend, the customers affected (with shared fraud), behavioral patterns, and the top fraud transactions. Use this when the user asks for a 'report', 'investigation', 'deep dive', or 'full picture' on a merchant.",
            "parameters": {
                "type": "object",
                "properties": {
                    "merchant_name": {
                        "type": "string",
                        "description": "Merchant name to investigate. Partial match supported — the tool resolves to the merchant with the most fraud matching the pattern. Pass a real merchant_name from get_risk_dashboard, never a placeholder."
                    },
                    "max_counterparties": {
                        "type": "integer",
                        "description": "Max affected customers to include (default 25, max 100)"
                    },
                    "max_transactions": {
                        "type": "integer",
                        "description": "Max top fraud transactions to include (default 20, max 100)"
                    }
                },
                "required": ["merchant_name"],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trace_fraud_network",
            "description": "Trace the fraud network around a merchant or customer. Given a seed merchant or user, returns the connected counterparties (users who transacted with the merchant, or merchants a user transacted with), highlighting fraud overlap and shared patterns. Use when the user asks to trace fraud from a merchant to its customers, identify which users were affected by a merchant, which merchants a user touched, or to map a fraud ring.",
            "parameters": {
                "type": "object",
                "properties": {
                    "merchant_name": {
                        "type": "string",
                        "description": "Seed merchant to trace outward from (either this or user_id is required). Must be a real merchant_name string from the database — typically a value returned by get_risk_dashboard(group_by='merchant'). Do NOT pass a tool name or a placeholder."
                    },
                    "user_id": {
                        "type": "integer",
                        "description": "Seed user to trace outward from"
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["merchant_to_users", "user_to_merchants", "auto"],
                        "description": "Which direction to trace. 'auto' picks based on seed type."
                    },
                    "fraud_only": {
                        "type": "boolean",
                        "description": "Restrict the trace to fraudulent transactions only (default true)"
                    },
                    "max_counterparties": {
                        "type": "integer",
                        "description": "Max connected counterparties to return (default 25)"
                    }
                },
                "required": [],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_training_data",
            "description": "Generate additional synthetic transactions for model retraining. The generated data is saved and can be used in a subsequent retrain_model call. Use when the user asks to generate data, create a training set, add synthetic transactions, or prepare data for retraining.",
            "parameters": {
                "type": "object",
                "properties": {
                    "n_transactions": {
                        "type": "integer",
                        "description": "Number of synthetic transactions to generate (min 1000, max 500000). Pass the exact number the user requests."
                    }
                },
                "required": ["n_transactions"],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "retrain_model",
            "description": "Start a model retraining experiment in the background. Trains a new XGBoost model using the base training data, optionally augmented with label corrections and/or generated synthetic data. Use when the user asks to retrain, run an experiment, or rebuild the model.",
            "parameters": {
                "type": "object",
                "properties": {
                    "use_corrections": {
                        "type": "boolean",
                        "description": "Include human label corrections in training (default true)"
                    },
                    "use_generated_data": {
                        "type": "boolean",
                        "description": "Include previously generated synthetic data in training (default true). Call generate_training_data first if no data has been generated yet."
                    },
                    "description": {
                        "type": "string",
                        "description": "Short description of this experiment for tracking purposes"
                    }
                },
                "required": [],
            }
        }
    },
]
