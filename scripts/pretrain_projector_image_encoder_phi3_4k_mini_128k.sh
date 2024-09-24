#!/bin/sh


export DATASET_DIR=playground/data

BASE_LLM_PATH=.cache/Phi-3-mini-4k-instruct-previous-version
IMAGE_VISION_TOWER=.cache/clip-vit-large-patch14-336
PROJECTOR_TYPE=mlp2x_gelu
OUTPUT_DIR_PATH=results/phi3_mini_4k_128k_pretrain/mlp2x_gelu_clip_l14_336px

CUDA_VISIBLE_DEVICES=6 deepspeed videogpt_plus/train/pretrain.py \
--deepspeed scripts/zero2.json \
--tune_image_mm_mlp_adapter True \
--model_name_or_path "$BASE_LLM_PATH" \
--version plain \
--dataset_use PRETRAINING \
--image_vision_tower "$IMAGE_VISION_TOWER" \
--image_mm_projector_type "$PROJECTOR_TYPE" \
--mm_vision_select_layer -2 \
--mm_use_im_start_end False \
--mm_use_im_patch_token False \
--bf16 True \
--output_dir $OUTPUT_DIR_PATH \
--num_train_epochs 1 \
--per_device_train_batch_size 16 \
--per_device_eval_batch_size 4 \
--gradient_accumulation_steps 2 \
--evaluation_strategy "no" \
--save_strategy "steps" \
--save_steps 50000 \
--save_total_limit 1 \
--learning_rate 1e-3 \
--weight_decay 0. \
--warmup_ratio 0.03 \
--lr_scheduler_type "cosine" \
--logging_steps 1 \
--tf32 True \
--model_max_length 4096 \
--gradient_checkpointing True \
--dataloader_num_workers 4 \
--lazy_preprocess True \
--report_to none
