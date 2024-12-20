from .dataset_config import *

DataConfig = {
    "PRETRAINING": [CC3M_595K, COCO_CAP, COCO_REG, COCO_REC],

    "STAGE1":[MOMENTOR],

    "STAGE2":[CLASSIFICATION_SSV2,CLASSIFICATION_K710,REASONING_CLEVRER_QA,REASONING_CLEVRER_MC,CONV_VideoChat1],

    "STAGE2_Momentor":[MOMENTOR_QA, CLASSIFICATION_K710, CLASSIFICATION_SSV2,REASONING_CLEVRER_QA,REASONING_CLEVRER_MC],

    "STAGE2WithMomentorQA":[MOMENTOR_CAP_QA,CLASSIFICATION_SSV2,CLASSIFICATION_K710,REASONING_CLEVRER_QA,REASONING_CLEVRER_MC,CONV_VideoChat1],

    "FINETUNING": [CONV_VideoChatGPT, VCG_HUMAN, VCG_PLUS_112K, CAPTION_VIDEOCHAT, CLASSIFICATION_K710, CLASSIFICATION_SSV2, CONV_VideoChat1, REASONING_NExTQA, REASONING_CLEVRER_QA, REASONING_CLEVRER_MC, VQA_WEBVID_QA],

    "VCGBench_FINETUNING": [CONV_VideoChatGPT, VCG_HUMAN, VCG_PLUS_112K, CAPTION_VIDEOCHAT, CONV_VideoChat1, VQA_WEBVID_QA],
    "MVBench_FINETUNING": [CLASSIFICATION_K710, CLASSIFICATION_SSV2, CONV_VideoChatGPT, REASONING_NExTQA, REASONING_CLEVRER_QA, REASONING_CLEVRER_MC, VQA_WEBVID_QA],

}
