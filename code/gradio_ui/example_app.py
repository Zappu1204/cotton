import gradio as gr
import subprocess
import os
import shutil
import fnmatch
import time
from PIL import Image

def copy_file_by_name(src_dir, dst_dir, file_name):
    """
    Copy all files with a specific name from one directory to another.
    Keep the same structure folder origin.
    Args:
        src_dir: Source directory.
        dst_dir: Destination directory.
        file_name: File name to copy.
    """
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if fnmatch.fnmatch(file, file_name):
                src_file = os.path.join(root, file)
                dst_file = os.path.join(dst_dir, os.path.relpath(src_file, src_dir))
                dst_file_dir = os.path.dirname(dst_file)
                if not os.path.exists(dst_file_dir):
                    os.makedirs(dst_file_dir)
                shutil.copyfile(src_file, dst_file)

def inference(brand):
    if not brand:
        return Image.new("RGB", (224, 224)), "Please input a brand."
    try:
        mode, elapsed_time = run_inference(brand)
        passage = f"Inference completed in {elapsed_time} seconds."
        # code/main/result/Top_1024x768_COTTON/inference/Gradio1/1/0.jpg
        global choose_product_name
        if choose_product_name is not None:
            output_image_path = os.path.join(cotton_dir, "code/main/result/Top_1024x768_COTTON", mode, brand, "1", choose_product_name)
        else:
            output_image_path = os.path.join(cotton_dir, "code/main/result/Top_1024x768_COTTON", mode, brand, "1", "0.jpg")
        output_image = Image.open(output_image_path)
        return output_image, passage
    except subprocess.CalledProcessError as e:
        passage = f"An error occurred: {e}"
        image = Image.new("RGB", (224, 224))
        return image, passage

def run_inference(brand):
    start_time = time.time()
    # Data/Training_Dataset/1024x768/example_gradio
    mode = "inference"
    gradio_txt = os.path.join(Data_path, dataset_name, brand, "gradio.txt")

    if choose_model_name is not None and choose_product_name is not None:
        choose_model_path = os.path.join(example_path, "model")
        new_model_path = os.path.join(Data_path, dataset_name, brand, "model")
        copy_file_by_name(choose_model_path, new_model_path, choose_model_name[0]+'*')
        choose_product_path = os.path.join(example_path, "product")
        new_product_path = os.path.join(Data_path, dataset_name, brand, "product")
        copy_file_by_name(choose_product_path, new_product_path, choose_product_name[0]+'*')
        mode = "gradio"
        content = f"{choose_model_name} {choose_product_name}"
        with open(gradio_txt, "w") as f:
            f.write(content)
    elif choose_model_name is not None and choose_product_name is None:
        choose_model_path = os.path.join(example_path, "model")
        new_model_path = os.path.join(Data_path, dataset_name, brand, "model")
        copy_file_by_name(choose_model_path, new_model_path, choose_model_name[0]+'*')
        mode = "gradio"
        content = f"{choose_model_name} 0.jpg"
        with open(gradio_txt, "w") as f:
            f.write(content)
    elif choose_product_name is not None and choose_model_name is None:
        choose_product_path = os.path.join(example_path, "product")
        new_product_path = os.path.join(Data_path, dataset_name, brand, "product")
        copy_file_by_name(choose_product_path, new_product_path, choose_product_name[0]+'*')
        mode = "gradio"
        content = f"0.jpg {choose_product_name}"
        with open(gradio_txt, "w") as f:
            f.write(content)
        
    os.chdir(os.path.join(cotton_dir, "code", "main"))

    print("========= Virtual Try-on =========")
    subprocess.run([
        "python", "main.py",
        "--config", "configs/config_top_COTTON.yaml",
        "--mode", mode,
        "--brand", brand
    ], check=True)

    end_time = time.time()
    inference_elapsed_time = end_time - start_time
    print(f"Total inference execution time: {inference_elapsed_time} seconds")

    return mode, inference_elapsed_time

def preprocess_model(model, brand):
    if not brand:
        return "Please input a brand."
    
    global choose_model_name
    choose_model_name = None

    brand_path = os.path.join(Data_path, brand, "VTON_Test_Gradio")
    model_dir = os.path.join(brand_path, "model")
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)
    else:
        for file in os.listdir(model_dir):
            os.remove(os.path.join(model_dir, file))
    model.save(os.path.join(model_dir, "01_model.jpg"))

    try:
        elapsed_time = run_preprocess_model(brand)
        return f"Preprocessing model completed in {elapsed_time} seconds."
    except subprocess.CalledProcessError as e:
        return f"An error occurred: {e}"    

def run_preprocess_model(brand):
    start_time = time.time()
    os.chdir(preprocess_dir)

    print(f"========= Find pose for {brand} =========")
    # Start Docker container
    subprocess.run(["docker", "start", "openpose"], check=True)
    # Execute find_pose.sh inside Docker
    subprocess.run([
        "docker", "exec", "-it", "openpose", "bash", "-c",
        f"bash find_pose.sh -b {brand}"
    ], check=True)

    # Run Python scripts
    print("========= Openpose Select =========")
    subprocess.run(["python", "openpose_select.py", "--brand", brand], check=True)

    print("========= CIHP Parsing =========")
    os.chdir(os.path.join(preprocess_dir, "CIHP_PARSING"))
    subprocess.run([
        "python", "human_parse.py",
        "--brand", brand
    ], check=True)
    os.chdir(preprocess_dir)

    print("========= Parse Select =========")
    subprocess.run(["python", "parse_select.py", "--brand", brand], check=True)

    print("========= ATR Generation and Parsing Merge =========")
    os.chdir(os.path.join(preprocess_dir, "Self-Correction-Human-Parsing"))
    subprocess.run([
        "python", "simple_extractor_for_preprocessing.py",
        "--dataset", "atr",
        "--model-restore", "exp-schp-201908301523-atr.pth",
        "--brand", brand
    ], check=True)
    os.chdir(preprocess_dir)

    print("========= Merge Label =========")
    subprocess.run(["python", "mergeLabel.py", "--brand", brand], check=True)

    print("========= Build Data Gradio Demo =========")
    subprocess.run([
        "python", "build_data_gradio_demo.py",
        "--brand", brand,
        "--mode", "p_model",
        "--h", "1024",
        "--w", "768"
    ], check=True)

    print("========= Build Data Gradio Demo =========")
    subprocess.run([
        "python", "build_data_gradio_demo.py",
        "--brand", brand,
        "--mode", "train_val_split",
        "--h", "1024",
        "--w", "768"
    ], check=True)

    end_time = time.time()
    preprocess_model_elapsed_time = end_time - start_time
    # print(f"Total preprocessing model execution time: {preprocess_model_elapsed_time} seconds")

    return preprocess_model_elapsed_time

def preprocess_product(product, brand):
    if not brand:
        return "Please input a brand."

    global choose_product_name
    choose_product_name = None

    brand_path = os.path.join(Data_path, brand, "VTON_Test_Gradio")
    product_dir = os.path.join(brand_path, "product")
    if not os.path.exists(product_dir):
        os.makedirs(product_dir)
    else:
        for file in os.listdir(product_dir):
            os.remove(os.path.join(product_dir, file))
    product.save(os.path.join(product_dir, "01_product.jpg"))

    try:
        product_elapsed_time = run_preprocess_product(product_dir, brand)
        return f"Preprocessing product completed in {product_elapsed_time} seconds."
    except subprocess.CalledProcessError as e:
        return f"An error occurred: {e}"

def run_preprocess_product(product_dir, brand):
    start_time = time.time()
    parser_path = os.path.join(cotton_dir, "Data", "parse_filtered_Data", brand, "VTON_Test_Gradio")
    if not os.path.exists(parser_path):
        os.makedirs(parser_path)
    else:
        for dir in os.listdir(parser_path):
            # subprocess.run([
            #     "rm", "-r", os.path.join(parser_path, dir)
            # ], check=True)
            shutil.rmtree(os.path.join(parser_path, dir))
    print(parser_path)

    print("Copy from" + product_dir + " to " + parser_path)
    # subprocess.run([
    #     "cp", "-r", product_dir, parser_path
    # ], check=True)
    shutil.copytree(product_dir, parser_path)

    print("========= Product mask generation (U2Net) =========")
    os.chdir(os.path.join(preprocess_dir, "U2Net"))
    subprocess.run([
        "python", "u2net_test.py", 
        "--brand", brand,

    ], check=True)
    os.chdir(preprocess_dir)

    print("========= Product Classification =========")
    os.chdir(os.path.join(preprocess_dir, "Sleeve_Classifier"))
    subprocess.run([
        "python", "main.py",
        "--mode", "preprocess",
        "--brand", brand
    ], check=True)
    os.chdir(preprocess_dir)

    print("========= Build Data Gradio Demo =========")
    subprocess.run([
        "python", "build_data_gradio_demo.py",
        "--brand", brand,
        "--mode", "p_product",
        "--h", "1024",
        "--w", "768"
    ], check=True)

    print("========= Cloth2Skeleton =========")
    os.chdir(os.path.join(preprocess_dir, "Cloth2Skeleton"))
    subprocess.run([
        "python", "main.py",
        "--mode", "test",
        "--config", "configs/config_top_v2_allData_augT.yaml",
        "--brand", brand
    ], check=True)
    os.chdir(preprocess_dir)

    print("========= ClothSegmentation =========")
    os.chdir(os.path.join(preprocess_dir, "ClothSegmentation"))
    subprocess.run([
        "python", "main.py",
        "--mode", "test",
        "--brand", brand
    ], check=True)
    os.chdir(preprocess_dir)

    end_time = time.time()
    preprocess_product_elapsed_time = end_time - start_time
    print(f"Total preprocessing product execution time: {preprocess_product_elapsed_time} seconds")

    return preprocess_product_elapsed_time

def info_model(img, model_name):
    global choose_model_name
    choose_model_name = os.path.basename(model_name)
    return choose_model_name

def info_product(img, product_name):
    global choose_product_name
    choose_product_name = os.path.basename(product_name)
    return choose_product_name

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cotton_size_does_matter_dir = os.path.dirname(os.path.dirname(script_dir))
    global cotton_dir
    cotton_dir = cotton_size_does_matter_dir
    global preprocess_dir
    preprocess_dir = os.path.join(cotton_dir, "code", "preprocessing")
    global Data_path
    Data_path = os.path.join(cotton_dir, "Data")

    # Data/Training_Dataset/1024x768/example_gradio
    global example_gradio_brand
    example_gradio_brand = "example_gradio"
    global dataset_name
    dataset_name = "Training_Dataset/1024x768"
    global example_path
    example_path = os.path.join(Data_path, dataset_name, example_gradio_brand)

    global choose_model_name
    choose_model_name = None

    global choose_product_name
    choose_product_name = None

    example_model_list = []
    example_product_list = []
    example_model_path = os.path.join(example_path, "model", "human_model")
    example_product_path = os.path.join(example_path, "product", "product")
    for model in os.listdir(example_model_path):
        if model.endswith(".jpg"):
            example_model_list.append([os.path.join(example_model_path, model), model])
    for product in os.listdir(example_product_path):
        if product.endswith(".jpg"):
            example_product_list.append([os.path.join(example_product_path, product), product])

    with gr.Blocks() as demo:
        gr.Markdown("# Virtual Try-on")
        
        with gr.Row():
            brand_input = gr.Textbox(label="Brand", placeholder="Input to brand", value="gradio_demo1")

        with gr.Row():
            with gr.Column():
                model_input = gr.Image(type="pil", label="Upload Model img")
                model_button = gr.Button("Preprocess Model")
                model_message = gr.Textbox(label="Model Notification", interactive=False)
                model_name = gr.Textbox(label="Model Name", placeholder="Input to model name", visible=False)
                example = gr.Examples(
                    inputs=[model_input, model_name],
                    examples_per_page=10,
                    examples=example_model_list,
                    label="Example Models",
                    run_on_click=True,
                    fn = info_model
                )
            with gr.Column():
                product_input = gr.Image(type="pil", label="Upload Product img",)
                product_button = gr.Button("Preprocess Product")
                product_message = gr.Textbox(label="Product Notification", interactive=False)
                product_name = gr.Textbox(label="Product Name", placeholder="Input to product name", visible=False)
                example = gr.Examples(
                    inputs=[product_input, product_name],
                    examples_per_page=10,
                    examples=example_product_list,
                    label="Example Products",
                    run_on_click=True,
                    fn = info_product
                )
            with gr.Column():
                output_image = gr.Image(label="Result img")
                inference_button = gr.Button("Inference")
                output_message = gr.Textbox(label="Infernce Notification", interactive=False)

        product_button.click(
            preprocess_product,
            inputs=[product_input, brand_input],
            outputs=[product_message]
        )

        model_button.click(
            preprocess_model,
            inputs=[model_input, brand_input],
            outputs=[model_message]
        )

        inference_button.click(
            inference,
            inputs=[brand_input],
            outputs=[output_image, output_message]
        )

    demo.launch(share=False)

if __name__ == "__main__":
    main()