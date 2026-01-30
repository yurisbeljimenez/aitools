#!/usr/bin/env python3
import os
import sys
import torch
import typer
from pathlib import Path
from PIL import Image
from rich.console import Console
from rich.panel import Panel
from rich.progress import track

# Suppress HF/TF warnings
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3" 

MODEL_ID = "microsoft/Florence-2-large"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

app = typer.Typer(help="aicap: LoRA Captioner for AI Influencers", no_args_is_help=True)
console = Console()

def load_model():
    """Load model with strict version compatibility and eager attention."""
    try:
        from transformers import AutoProcessor, AutoModelForCausalLM
        
        with console.status("[bold green]Loading Florence-2 Large...[/bold green]"):
            # attn_implementation="eager" is critical to avoid SDPA attribute errors
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_ID, 
                trust_remote_code=True, 
                attn_implementation="eager",
                torch_dtype=torch.float16
            ).to(DEVICE).eval()
            
            processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
        return model, processor
    except Exception as e:
        console.print(f"[bold red]❌ Model Load Error:[/bold red] {e}")
        sys.exit(1)

@app.command()
def run(
    folder: Path = typer.Argument(..., help="Folder with training images", exists=True, file_okay=False, resolve_path=True),
    trigger: str = typer.Argument(..., help="LoRA trigger word (e.g. 'novak4i')"),
    force: bool = typer.Option(True, "--force/--skip", help="Overwrite existing .txt files?"),
):
    """Generate character-focused captions for FLUX LoRA training."""
    console.print(Panel(
        f"🚀 [bold]LoRA Captioning Mode v2.3[/bold]\n"
        f"📂 Dataset: [blue]{folder}[/blue]\n"
        f"🔑 Trigger: [green]{trigger}[/green]\n"
        f"⚙️  Device: [yellow]{DEVICE}[/yellow]", 
        title="AI Influencer Tools"
    ))

    model, processor = load_model()

    valid_exts = {'.png', '.jpg', '.jpeg', '.webp'}
    images = [f for f in sorted(os.listdir(folder)) if f.lower().endswith(tuple(valid_exts))]
    
    if not images:
        console.print("[yellow]⚠️  No images found.[/yellow]")
        raise typer.Exit()

    task = "<MORE_DETAILED_CAPTION>"
    count = 0

    for filename in track(images, description="[cyan]Processing dataset...[/cyan]"):
        img_path = folder / filename
        txt_path = folder / (img_path.stem + ".txt")

        if not force and txt_path.exists():
            continue

        try:
            # Explicitly convert to RGB and resize to ensure processor has data
            raw_image = Image.open(img_path).convert("RGB")
            
            # Using the processor with explicit return_tensors
            inputs = processor(text=task, images=raw_image, return_tensors="pt")
            
            # Manual dictionary unpacking to ensure tensors are on GPU
            input_dict = {
                "input_ids": inputs["input_ids"].to(DEVICE),
                "pixel_values": inputs["pixel_values"].to(DEVICE, torch.float16)
            }

            with torch.no_grad():
                generated_ids = model.generate(
                    **input_dict,
                    max_new_tokens=1024,
                    num_beams=3,
                    do_sample=False
                )
            
            generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
            parsed = processor.post_process_generation(
                generated_text, 
                task=task, 
                image_size=(raw_image.width, raw_image.height)
            )
            description = parsed[task]

            # LoRA-Specific: Subject disentanglement
            # Replaces 'A woman/A person' with your trigger word
            final_caption = description.replace("A woman", trigger).replace("a woman", trigger).replace("A person", trigger)
            
            # Fallback to prepend trigger if replacement didn't happen
            if trigger not in final_caption:
                final_caption = f"{trigger}, {final_caption}"

            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(final_caption.strip())
            
            count += 1
            
        except Exception as e:
            console.print(f"[red]Error on {filename}: {e}[/red]")

    console.print(f"[bold green]✅ Success! {count} captions prepared for Flux training.[/bold green]")

if __name__ == "__main__":
    app()