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

# Suppress HF warnings
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3" 

# --- CONFIG ---
MODEL_ID = "microsoft/Florence-2-large"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

app = typer.Typer(help="aicap: Florence-2 Auto Captioner", no_args_is_help=True)
console = Console()

def load_model():
    """Lazy load the model only when command is run."""
    try:
        from transformers import AutoProcessor, AutoModelForCausalLM
        
        with console.status("[bold green]Loading Florence-2 Model...[/bold green]"):
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_ID, 
                trust_remote_code=True, 
                torch_dtype=torch.float16
            ).to(DEVICE).eval()
            processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
        return model, processor
    except ImportError:
        console.print("[bold red]❌ Error: Libraries not found. Check venv.[/bold red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]❌ Model Load Error:[/bold red] {e}")
        sys.exit(1)

@app.command()
def run(
    folder: Path = typer.Argument(..., help="Folder containing images", exists=True, file_okay=False, resolve_path=True),
    trigger: str = typer.Argument(..., help="Trigger word to prefix captions (e.g. 'novak4i')"),
    force: bool = typer.Option(True, "--force/--skip", help="Overwrite existing captions?"),
):
    """
    Generate detailed captions for all images in a folder using Florence-2.
    """
    console.print(Panel(f"📂 Scanning: [bold blue]{folder}[/bold blue]\n🔑 Trigger: [bold green]{trigger}[/bold green]\n⚙️  Device: [yellow]{DEVICE}[/yellow]", title="AI Captioner"))

    # 1. Load Model
    model, processor = load_model()

    # 2. Collect Images
    valid_exts = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
    images = [f for f in sorted(os.listdir(folder)) if f.lower().endswith(tuple(valid_exts))]
    
    if not images:
        console.print("[yellow]⚠️  No images found in folder.[/yellow]")
        raise typer.Exit()

    # 3. Process Loop
    count = 0
    task = "<MORE_DETAILED_CAPTION>"

    for filename in track(images, description="[cyan]Captioning images...[/cyan]"):
        img_path = folder / filename
        txt_path = folder / (img_path.stem + ".txt")

        # Skip if exists and not forcing
        if not force and txt_path.exists():
            continue

        try:
            image = Image.open(img_path).convert("RGB")
        except Exception as e:
            console.print(f"[red]Error reading {filename}: {e}[/red]")
            continue

        # Generate Caption
        try:
            inputs = processor(text=task, images=image, return_tensors="pt").to(DEVICE, torch.float16)
            
            with torch.no_grad():
                generated_ids = model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=1024,
                    num_beams=3
                )
            
            generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
            parsed_answer = processor.post_process_generation(
                generated_text, 
                task=task, 
                image_size=(image.width, image.height)
            )
            description = parsed_answer[task]
            
            # Save file
            final_caption = f"{trigger}, {description}"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(final_caption)
            
            count += 1
            
        except Exception as e:
            console.print(f"[red]Inference failed on {filename}: {e}[/red]")

    console.print(f"[bold green]🎉 Done! Updated {count} images.[/bold green]")

if __name__ == "__main__":
    app()