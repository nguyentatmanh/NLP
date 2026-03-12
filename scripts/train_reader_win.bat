@echo off
python train_reader.py --model_name xlm-roberta-base --output_dir .\outputs\uit_reader_xlmr --num_train_epochs 1 --per_device_train_batch_size 4 --per_device_eval_batch_size 8 --fp16
