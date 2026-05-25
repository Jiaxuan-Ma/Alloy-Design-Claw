# Alloy Design Claw

**Alloy Design Claw** is a prototype agent tool for intelligent design of Superalloys. The project provides a web-based conversational interface and uses local Skills workflows to connect data validation, thermodynamic calculations, machine-learning modeling, SHAP-based feature selection, NSGA-III multi-objective optimization, and optional mechanical-property screening.

<img width="2289" height="1187" alt="image" src="https://github.com/user-attachments/assets/96ed60cc-a019-463c-8543-697b96a6023c" />


## Key Features

* Upload and validate alloy composition datasets.
* Run Thermo-Calc/TC-Python workflows to calculate thermophysical properties.
* Train and compare multiple regression models, with automatic selection of the best-performing model.
* Use SHAP analysis to identify key alloying elements.
* Perform multi-objective composition optimization based on NSGA-III.
* Optionally filter optimized compositions using predicted UTS and elongation results.

## Project Structure

```text
.
├── app.py                  # Web service entry point and Agent UI backend
├── base_agent.py           # LangChain Agent and Skills invocation logic
├── main.ipynb              # Notebook entry point for experiments
├── dataset.xlsx            # Sample dataset
├── web/                    # Frontend pages, styles, and interaction scripts
└── Skills/                 # Alloy-design-related skills and scripts
```

## Environment Setup

Python 3.10 or later is recommended. Install the required dependencies with:

```bash
pip install python-dotenv pyyaml requests html2text pandas openpyxl scikit-learn joblib langchain langchain-core langchain-deepseek
```

To run the full optimization and explainability workflow, also install:

```bash
pip install shap pymoo
```

Thermo-Calc-related features require a working local Thermo-Calc/TC-Python environment and a valid license.

## Configuration

Create or edit a `.env` file in the project root directory and add the model service settings:

```env
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

To specify the Python environment used by the Agent, you may additionally set:

```env
AGENT_PYTHON=D:\anaconda3\envs\pytorch_gpu\python.exe
```

## Getting Started

Run the following command from the project root directory:

```bash
python app.py 8000
```

Then open the following address in your browser:

```text
http://127.0.0.1:8000
```

## Basic Workflow

1. Open the web interface and upload an alloy dataset.
2. Ask the Agent to validate the composition columns and generate a composition-only working file.
3. Run thermodynamic calculations to obtain a dataset labeled with thermophysical properties.
4. Train prediction models and select the best-performing thermophysical-property model.
5. Run SHAP analysis to identify the alloying elements for optimization.
6. Set element ranges and optimization parameters, then run NSGA-III optimization.
7. With available mechanical-property data, you can further train UTS/EL models and filter candidate alloys.

## Notes

This project is currently a local prototype. Some scripts depend on the user’s local Python environment, model service API key, and Thermo-Calc installation. Before running the project, make sure the `.env` file, required packages, and data files are properly prepared.

## Contact

Jiaxuan Ma, [jxma@sjtu.edu.cn](mailto:jxma@sjtu.edu.cn)
