import argparse
from tqdm import tqdm
import shortuuid
from videogpt_plus.conversation import conv_templates
from videogpt_plus.model.builder import load_pretrained_model
from videogpt_plus.mm_utils import tokenizer_image_token, get_model_name_from_path
from eval.egoschema.inference.ddp import *
from torch.utils.data import DataLoader, DistributedSampler
import traceback
import transformers
from transformers import StoppingCriteria, StoppingCriteriaList


def disable_torch_init():
    """
    Disable the redundant torch default initialization to accelerate model creation.
    """
    import torch
    setattr(torch.nn.Linear, "reset_parameters", lambda self: None)


def eval_model(args):
    # Model
    import random
    import numpy as np
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)
    torch.cuda.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    disable_torch_init()
    model_path = os.path.expanduser(args.model_path)
    model_name = get_model_name_from_path(args.model_path)
    tokenizer, model, image_processor, context_len = load_pretrained_model(model_path, args.model_base, model_name)
    if getattr(model.config,'mm_mamba',None) is not None:
        mamba_tokenizer = transformers.AutoTokenizer.from_pretrained(
                model.config.mm_mamba,
                padding_side="right")
    if getattr(model.config,'visual_token_compression_rate',None) is None:
        model.config.visual_token_compression_rate = 2
    model.config.stage = 2
    mm_use_im_start_end = getattr(model.config, "mm_use_im_start_end", False)
    mm_use_im_patch_token = getattr(model.config, "mm_use_im_patch_token", True)
    if mm_use_im_patch_token:
        tokenizer.add_tokens([DEFAULT_IMAGE_PATCH_TOKEN], special_tokens=True)
    if mm_use_im_start_end:
        tokenizer.add_tokens([DEFAULT_IM_START_TOKEN, DEFAULT_IM_END_TOKEN], special_tokens=True)
    model.resize_token_embeddings(len(tokenizer))

    vision_tower = model.get_vision_tower()
    vision_tower.load_model(model.config.mm_vision_tower)
    video_processor = vision_tower.image_processor

    image_vision_tower = model.get_image_vision_tower()
    image_vision_tower.load_model()
    image_processor = image_vision_tower.image_processor

    model = model.to("cuda")

    dataset = EvalDatasetEgoschema(args.question_dir, args.video_folder, image_processor,
                                 video_processor)
    # distributed_sampler = DistributedSampler(dataset, rank=args.rank, shuffle=False)
    # dataloader = DataLoader(dataset, batch_size=args.batch_size_per_gpu, num_workers=4, sampler=distributed_sampler)
    dataloader = DataLoader(dataset, batch_size=args.batch_size_per_gpu, num_workers=4, shuffle=False)

    answer_data = []
    for (idx, sample_set, video_frames, context_frames, slice_len) in tqdm(dataloader):
        idx, sample_set, video_frames, context_frames, slice_len = int(idx[0]), sample_set[
            0], video_frames, context_frames, int(slice_len[0])
        #FIXME  there is a bug for some sample that can not sample 16 frames and is padded to 16 frames 
        slice_len = len(video_frames)
        sample = sample_set
        qs = sample['Q'][0]

        try:
            cur_prompt = qs
            if model.config.mm_use_im_start_end:
                qs = DEFAULT_IM_START_TOKEN + DEFAULT_IMAGE_TOKEN * slice_len + DEFAULT_IM_END_TOKEN + '\n' + qs
            else:
                qs = DEFAULT_IMAGE_TOKEN * slice_len + '\n' + qs

            conv = conv_templates[args.conv_mode].copy()
            conv.append_message(conv.roles[0], qs)
            conv.append_message(conv.roles[1], None)
            prompt = conv.get_prompt()

            input_ids = tokenizer_image_token(prompt, tokenizer, IMAGE_TOKEN_INDEX,
                                              return_tensors='pt').unsqueeze(0).cuda()
            
            input_ids_mamba = None
            if getattr(model.config,'mm_mamba',None) is not None:
                conv_mamba = conv_templates['mamba'].copy()
                conv_mamba.append_message(conv_mamba.roles[0], qs)
                conv_mamba.append_message(conv_mamba.roles[1], None)
                prompt = conv_mamba.get_prompt()

                input_ids_mamba = tokenizer_image_token(prompt, mamba_tokenizer, IMAGE_TOKEN_INDEX,
                                                return_tensors='pt').unsqueeze(0).cuda()

            # stop_str = conv.sep if conv.sep_style != SeparatorStyle.TWO else conv.sep2
            stop_str = "<|end|>"

            with torch.inference_mode():
                output_ids = model.generate(
                    input_ids_mamba=input_ids_mamba,
                    input_ids=input_ids,
                    images=torch.cat(video_frames, dim=0).to(torch.bfloat16).cuda(),
                    context_images=torch.cat(context_frames, dim=0).to(torch.bfloat16).cuda(),
                    do_sample=True if args.temperature > 0 else False,
                    temperature=args.temperature,
                    top_p=args.top_p,
                    num_beams=args.num_beams,
                    max_new_tokens=1024,
                    use_cache=True)

            input_token_len = input_ids.shape[1]
            n_diff_input_output = (input_ids != output_ids[:, :input_token_len]).sum().item()
            if n_diff_input_output > 0:
                print(f'[Warning] {n_diff_input_output} output_ids are not the same as the input_ids')
            outputs = tokenizer.batch_decode(output_ids[:, input_token_len:], skip_special_tokens=True)[0]
            outputs = outputs.strip()
            if outputs.endswith(stop_str):
                outputs = outputs[:-len(stop_str)]
            outputs = outputs.strip()
            outputs = outputs.replace("<|end|>", '')
            outputs = outputs.strip()

            results = {"question uid": sample['video_name'][0],
                       "answer": outputs,}
            answer_data.append(results)

        except Exception as e:
            trace = traceback.format_exc()
            print(f"Error processing video file '{sample['video_name'][0]}': {e}")
            print("Detailed traceback:")
            print(trace)
    with open(f"{args.output_dir}", "w") as f:
        json.dump(answer_data, f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=str, default="MBZUAI/VideoGPT-plus_Phi3-mini-4k/mvbench")
    parser.add_argument("--model-base", type=str, default="microsoft/Phi-3-mini-4k-instruct")
    parser.add_argument("--video-folder", type=str, default="OpenGVLab/MVBench/video")
    parser.add_argument("--question-dir", type=str, default="OpenGVLab/MVBench/json")
    parser.add_argument("--output-dir", type=str, default="MBZUAI/VideoGPT-plus_Phi3-mini-4k/mvbench_eval")
    parser.add_argument("--conv-mode", type=str, default="phi3_instruct")
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--top_p", type=float, default=None)
    parser.add_argument("--num_beams", type=int, default=1)

    parser.add_argument("--batch_size_per_gpu", required=False, default=1)
    parser.add_argument('--world_size', default=1, type=int, help='number of distributed processes')
    parser.add_argument('--local_rank', default=-1, type=int)
    parser.add_argument('--dist_url', default='env://', help='url used to set up distributed training')

    args = parser.parse_args()

    init_distributed_mode(args)

    # os.makedirs(args.output_dir, exist_ok=True)

    eval_model(args)
