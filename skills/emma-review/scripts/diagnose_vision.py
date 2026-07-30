#!/usr/bin/env python3
"""
Diagnostic script to debug Qwen3-VL + MLX-VLM generation issues.
Tests multiple configurations to find a working setup.

Usage (run from project root in a real Mac terminal):

    .venv-emma-review/bin/python skills/emma-review/scripts/diagnose_vision.py \
        --image "/path/to/any/frame.jpg"
"""

import argparse
import os
import sys
import time
import traceback


def main():
    parser = argparse.ArgumentParser(description="Diagnose Qwen3-VL + MLX-VLM issues")
    parser.add_argument("--model", default=os.path.expanduser(
        "~/Library/Caches/emma-review/models/Qwen3-VL-4B-Instruct-4bit"))
    parser.add_argument("--image", required=True, help="Path to a single test image")
    parser.add_argument("--num-images", type=int, default=1, help="Number of images")
    args = parser.parse_args()

    from mlx_vlm import load, apply_chat_template, generate
    from mlx_vlm.utils import load_config
    import mlx.core as mx

    print(f"Loading model from {args.model}...")
    model, processor = load(args.model)
    config = load_config(args.model)
    tokenizer = processor.tokenizer

    # Show key token IDs
    print(f"\n--- Tokenizer Info ---")
    print(f"  eos_token: {tokenizer.eos_token} (id={tokenizer.eos_token_id})")
    print(f"  pad_token: {tokenizer.pad_token} (id={tokenizer.pad_token_id})")

    # Check for thinking tokens
    for tid in [151643, 151645, 151667, 151668]:
        try:
            tok = tokenizer.convert_ids_to_tokens(tid)
            print(f"  token_id {tid}: {repr(tok)}")
        except:
            pass

    image_paths = [args.image] * args.num_images

    # Test configurations to try
    tests = [
        {
            "name": "1. Simple string prompt, temp=0.0, no thinking",
            "prompt": "What do you see in this image? Describe it briefly.",
            "kwargs": {"temperature": 0.0, "max_tokens": 256, "enable_thinking": False},
        },
        {
            "name": "2. Simple string prompt, temp=0.7, no thinking",
            "prompt": "What do you see in this image? Describe it briefly.",
            "kwargs": {"temperature": 0.7, "max_tokens": 256, "enable_thinking": False},
        },
        {
            "name": "3. Simple string prompt, temp=0.7, thinking enabled",
            "prompt": "What do you see in this image? Describe it briefly.",
            "kwargs": {"temperature": 0.7, "max_tokens": 512, "enable_thinking": True},
        },
        {
            "name": "4. Chinese prompt, temp=0.7, no thinking",
            "prompt": "请描述这张图片中的内容。",
            "kwargs": {"temperature": 0.7, "max_tokens": 256, "enable_thinking": False},
        },
        {
            "name": "5. Short prompt, temp=0.7, top_p=0.8, top_k=20 (matching gen config)",
            "prompt": "Describe this image.",
            "kwargs": {"temperature": 0.7, "max_tokens": 256, "enable_thinking": False,
                       "top_p": 0.8, "top_k": 20},
        },
    ]

    for test in tests:
        print(f"\n{'='*60}")
        print(f"  {test['name']}")
        print(f"{'='*60}")

        try:
            messages = [{"role": "user", "content": test["prompt"]}]

            # Try formatting with num_images
            try:
                formatted = apply_chat_template(
                    processor, config, messages,
                    add_generation_prompt=True,
                    num_images=len(image_paths),
                )
            except Exception as e:
                print(f"  apply_chat_template with num_images failed: {e}")
                print(f"  Trying without num_images...")
                formatted = apply_chat_template(
                    processor, config, messages,
                    add_generation_prompt=True,
                )

            # Show if image tokens are in the prompt
            has_image_token = "<|image_pad|>" in formatted or "<|vision_start|>" in formatted
            print(f"  Prompt length: {len(formatted)} chars")
            print(f"  Image tokens in prompt: {has_image_token}")
            print(f"  Prompt ends with: ...{repr(formatted[-80:])}")

            # Show the prompt tokens count
            token_ids = tokenizer.encode(formatted)
            print(f"  Token count: {len(token_ids)}")

            t0 = time.time()
            result = generate(
                model, processor,
                prompt=formatted,
                image=image_paths,
                verbose=False,
                **test["kwargs"],
            )
            elapsed = time.time() - t0

            print(f"  Generation tokens: {result.generation_tokens}")
            print(f"  Time: {elapsed:.1f}s")
            print(f"  Peak memory: {result.peak_memory:.2f} GB")
            print(f"  Finish reason: {result.finish_reason}")
            print(f"  Output text: {repr(result.text[:500])}")

            if result.generation_tokens <= 2:
                print(f"  ⚠️  Very few tokens generated - likely immediate EOS")
            elif result.text.strip():
                print(f"  ✅ Got meaningful output!")
            else:
                print(f"  ⚠️  Generated tokens but empty text (maybe thinking tokens filtered?)")

        except Exception as e:
            print(f"  FAILED: {e}")
            traceback.print_exc()

    # Test 6: Try with get_message_json for proper multimodal formatting
    print(f"\n{'='*60}")
    print(f"  6. Using get_message_json for proper multimodal format")
    print(f"{'='*60}")

    try:
        from mlx_vlm import get_message_json

        # Get the model name for message formatting
        model_name = "qwen3_vl"
        msg = get_message_json(model_name, "What do you see in this image?", num_images=1)
        print(f"  Message JSON: {msg}")

        messages = [msg]
        formatted = apply_chat_template(
            processor, config, messages,
            add_generation_prompt=True,
            num_images=1,
        )
        print(f"  Prompt length: {len(formatted)} chars")
        has_image_token = "<|image_pad|>" in formatted or "<|vision_start|>" in formatted
        print(f"  Image tokens in prompt: {has_image_token}")

        t0 = time.time()
        result = generate(
            model, processor,
            prompt=formatted,
            image=image_paths[:1],
            max_tokens=256,
            temperature=0.7,
            enable_thinking=False,
            verbose=False,
        )
        elapsed = time.time() - t0
        print(f"  Generation tokens: {result.generation_tokens}")
        print(f"  Time: {elapsed:.1f}s")
        print(f"  Finish reason: {result.finish_reason}")
        print(f"  Output text: {repr(result.text[:500])}")

    except Exception as e:
        print(f"  FAILED: {e}")
        traceback.print_exc()

    # Test 7: Try stream_generate to see token-by-token
    print(f"\n{'='*60}")
    print(f"  7. Using stream_generate to see raw tokens")
    print(f"{'='*60}")

    try:
        from mlx_vlm import stream_generate

        messages = [{"role": "user", "content": "Describe this image."}]
        formatted = apply_chat_template(
            processor, config, messages,
            add_generation_prompt=True,
            num_images=1,
        )

        tokens_seen = 0
        text_parts = []
        t0 = time.time()
        for chunk in stream_generate(
            model, processor,
            prompt=formatted,
            image=image_paths[:1],
            max_tokens=64,
            temperature=0.7,
            enable_thinking=False,
        ):
            if chunk.token is not None:
                tokens_seen += 1
                tok_str = tokenizer.convert_ids_to_tokens(chunk.token)
                text_parts.append(chunk.text if hasattr(chunk, 'text') else str(tok_str))
                if tokens_seen <= 10:
                    print(f"    token {tokens_seen}: id={chunk.token} -> {repr(tok_str)}")
            if tokens_seen >= 10:
                break

        elapsed = time.time() - t0
        print(f"  Tokens seen (first 10): {tokens_seen}")
        print(f"  Time: {elapsed:.1f}s")
        print(f"  Joined text: {repr(''.join(text_parts)[:500])}")

    except Exception as e:
        print(f"  FAILED: {e}")
        traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"  Diagnosis complete. Review the outputs above.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
