@echo off
set MODEL_DIR=.\outputs\uit_reader_xlmr
set OUT_DIR=.\report_figures

python generate_experiment_charts_v2.py --model_dir "%MODEL_DIR%" --out_dir "%OUT_DIR%"
echo.
echo Da tao xong bieu do trong thu muc %OUT_DIR%
pause
