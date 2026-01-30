#!/usr/bin/env python3
import os
import sys
import torch
import typer
import re
from pathlib import Path
from PIL import Image
from rich.console import Console
from rich.panel import Panel
from rich.progress import track

# Suppress HF/TF warnings
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3" 

MODEL_ID = "microsoft/Florence-2-large"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

app = typer.Typer(help="aicap v3.5: Zero-Noise Production Tool", no_args_is_help=True)
console = Console()

def load_model():
    try:
        from transformers import AutoProcessor, AutoModelForCausalLM
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID, 
            trust_remote_code=True, 
            attn_implementation="eager", 
            torch_dtype=torch.float16
        ).to(DEVICE).eval()
        processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
        return model, processor
    except Exception as e:
        console.print(f"[bold red]❌ Load Error:[/bold red] {e}")
        sys.exit(1)

@app.command()
def run(
    folder: Path = typer.Argument(..., help="Dataset folder"),
    trigger: str = typer.Argument(..., help="Trigger word"),
    force: bool = typer.Option(True, "--force/--skip"),
    mapping: str = typer.Option(None, "--map", help="e.g. 'blonde=silver,grey=silver'"),
):
    """
    Final Polish.
    1. Scrub 'Overall mood' sentences.
    2. Fix 'bra and matching bra' stutters.
    3. Remove 'wavy hair... styled in waves' redundancy.
    """
    console.print(Panel(
        f"🚀 [bold]aicap v3.5[/bold] | 🔑 [green]{trigger}[/green] | 🛠️  [yellow]{mapping or 'Raw'}[/yellow]", 
        title="FLUX.2 Production Suite"
    ))

    replace_map = {}
    if mapping:
        for pair in mapping.split(","):
            if "=" in pair:
                k, v = pair.split("=")
                replace_map[k.strip().lower()] = v.strip().lower()

    model, processor = load_model()
    valid_exts = {'.png', '.jpg', '.jpeg'}
    images = [f for f in sorted(os.listdir(folder)) if f.lower().endswith(tuple(valid_exts))]
    
    task = "<MORE_DETAILED_CAPTION>"

    for filename in track(images, description="[cyan]Polishing Dataset...[/cyan]"):
        img_path = folder / filename
        txt_path = folder / (img_path.stem + ".txt")

        if not force and txt_path.exists():
            continue

        try:
            raw_image = Image.open(img_path).convert("RGB")
            inputs = processor(text=task, images=raw_image, return_tensors="pt")
            input_dict = {"input_ids": inputs["input_ids"].to(DEVICE), "pixel_values": inputs["pixel_values"].to(DEVICE, torch.float16)}
            
            with torch.no_grad():
                generated_ids = model.generate(**input_dict, max_new_tokens=1024, num_beams=3)
            
            generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
            description = processor.post_process_generation(generated_text, task=task, image_size=raw_image.size)[task]

            # --- 1. USER MAPPING (Expanded) ---
            # Do this FIRST to catch 'grey' before 'silver' processing
            clean_caption = description
            for old, new in replace_map.items():
                clean_caption = re.sub(r"\b" + re.escape(old) + r"\b", new, clean_caption, flags=re.IGNORECASE)

            # --- 2. STUTTER & REDUNDANCY FILTER (New in v3.5) ---
            # Fix "bra and matching bra"
            clean_caption = clean_caption.replace("bra and matching bra", "bra")
            clean_caption = clean_caption.replace("matching bra and matching bra", "matching bra")
            
            # Fix "wavy... styled in loose waves" redundancy
            # If we see "wavy" and "loose waves", kill the second part
            if "wavy" in clean_caption and "styled in loose waves" in clean_caption:
                clean_caption = clean_caption.replace(" that is styled in loose waves", "")
                clean_caption = clean_caption.replace(" styled in loose waves", "")

            # Fix pluralized clothes
            clean_caption = clean_caption.replace("The bodysuits are", "The bodysuit is")
            clean_caption = clean_caption.replace("The bodysuits have", "The bodysuit has")

            # --- 3. SMART SUBSTITUTION ---
            subject_patterns = [
                (r"\b[Aa] (?:young |beautiful |standing |posing |smiling )?woman\b", trigger),
                (r"\b[Tt]he (?:young |beautiful |standing |posing |smiling )?woman\b", trigger),
                (r"\b[Aa] (?:young |beautiful |smiling )?lady\b", trigger),
            ]
            for pat, repl in subject_patterns:
                clean_caption = re.sub(pat, repl, clean_caption)

            # --- 4. NOISE & MOOD SCRUBBER (Expanded) ---
            noise_patterns = [
                r"^The image is a [a-zA-Z\s]+ of ", 
                r"^The image shows ",
                r"^In this image, ",
                r"^Captured in this shot is ",
                r"^[Tt]he image depicts ",
                # New: Kill the mood sentences at the end
                r"The overall mood of the image is [a-zA-Z\s]+\.$",
                r"The overall mood of the image is [a-zA-Z\s]+\."
            ]
            for pat in noise_patterns:
                clean_caption = re.sub(pat, "", clean_caption).strip()

            # --- 5. FORMATTING ---
            clean_caption = clean_caption.strip(",. ")
            if not clean_caption.lower().startswith(trigger.lower()):
                clean_caption = f"{trigger}, {clean_caption}"
            if not clean_caption.endswith("."):
                clean_caption += "."

            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(clean_caption)
            
        except Exception as e:
            console.print(f"[red]Error on {filename}: {e}[/red]")

    console.print("[green]✅ Success! Captions scrubbed & polished.[/green]")

if __name__ == "__main__":
    app()