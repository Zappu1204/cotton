import gradio as gr
import subprocess
import os
import docker
import sys
from tqdm import tqdm
import yaml
import shutil
import fnmatch
import time
from PIL import Image
import cv2

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main.util.utils as utils

import torch

from torch.utils.data import DataLoader

from main.dataLoader import TryonDataset
from main.model_end2end import COTTON

from preprocessing.CIHP_PARSING.human_parse import ImageReader, decode_labels_inside

import tensorflow.compat.v1 as tf # type: ignore
tf.disable_v2_behavior()

N_CLASSES = 20

def parsing_init_():
    # Print GPUs available
    print(tf.config.list_physical_devices('GPU'))

    # Adjusting percentage of GPU available for tensorflow
    gpu_options = tf.GPUOptions(per_process_gpu_memory_fraction=0.5)#0.2)
    config = tf.ConfigProto(gpu_options=gpu_options)

    # Build graph with pre-saved graph and GPU settings
    parsing_graph = tf.Graph()
    with parsing_graph.as_default():
        od_graph_def = tf.GraphDef()
        with tf.gfile.GFile(FROZEN_MODEL_PATH, 'rb') as fid:
            serialized_graph = fid.read()
            od_graph_def.ParseFromString(serialized_graph)
            _ = tf.import_graph_def(od_graph_def, name='')
        parsing_sess = tf.Session(graph=parsing_graph, config=config)
        # Initialization
        init = tf.global_variables_initializer()
        parsing_sess.run(init)
    return parsing_sess, parsing_graph

def parsing_init(input_dir, parsing_graph, parsing_sess):
    data_list = os.listdir(input_dir)

    # Load reader.
    with parsing_graph.as_default():
        with tf.name_scope("create_inputs"):
            image, image_list = ImageReader(input_dir, data_list, None, None, False, False, False)
            image_rev = tf.reverse(image, tf.stack([1]))

        image_batch = tf.stack([image, image_rev])

    image_tensor_detect = parsing_graph.get_tensor_by_name('stack:0')
    pred_all = parsing_graph.get_tensor_by_name('ExpandDims_1:0')
    
    return image_tensor_detect, image_batch, pred_all, data_list

def cihp_parsing_gen(input_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'vis'), exist_ok=True)

    image_tensor_detect, image_batch, pred_all, data_list = parsing_init(input_dir, parsing_graph, parsing_sess)
    # For multi-thread processing
    print("=================Start multi-thread processing==============================")
    coord = tf.train.Coordinator()
    threads = tf.train.start_queue_runners(coord=coord, sess=parsing_sess)
    
    print("Start for")
    for step in range(len(data_list)):
        start_time = time.time()
        print("start eval")
        image_numpy = image_batch.eval(session=parsing_sess) 
        print("end eval")
        parsing_= parsing_sess.run(pred_all,feed_dict={image_tensor_detect: image_numpy})   
        print("end run")

        msk = decode_labels_inside(parsing_, num_classes=N_CLASSES)
        print("end decode")
        parsing_im = Image.fromarray(msk[0])
        file_id = data_list[step][:-4]
        parsing_im.save('{}/vis/{}.png'.format(output_dir, file_id))
        cv2.imwrite('{}/{}.png'.format(output_dir, file_id), parsing_[0,:,:,0])
        
        if step == 0:
            print("step {} | cost {} sec".format(step, time.time()-start_time))
        else:
            print("\r step [{}/{}] | cost {} sec".format(step, len(data_list), time.time()-start_time), end=" ")
        
    # # Stop all thread, ready to finish
    # coord.request_stop()
    # coord.join(threads)


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
    data_dir = os.path.join(Data_path, 'Training_Dataset/1024x768', brand)
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
        
    # os.chdir(os.path.join(cotton_dir, "code", "main"))

    # print("========= Virtual Try-on =========")
    # subprocess.run([
    #     "python", "main.py",
    #     "--config", "configs/config_top_COTTON.yaml",
    #     "--mode", mode,
    #     "--brand", brand
    # ], check=True)
    config['VAL_CONFIG']['DATA_DIR'] = data_dir
    config['MODE'] = mode
    dataset = TryonDataset(config)
    # dataloader = DataLoader(dataset, batch_size=config['VAL_CONFIG']['BATCH_SIZE'], \
    #                         shuffle=True, num_workers=config['TRAINING_CONFIG']['NUM_WORKER'])
    dataloader = DataLoader(
        dataset,
        batch_size=config['VAL_CONFIG']['BATCH_SIZE'],
        shuffle=True,
        num_workers=config['TRAINING_CONFIG']['NUM_WORKER'],
    )
    for step, batch in enumerate(tqdm(dataloader)):
        # Name
        c_name = batch["c_name"]

        # Input
        human_masked = batch['human_masked'].cuda()
        human_pose = batch['human_pose'].cuda()
        human_parse_masked = batch['human_parse_masked'].cuda()
        c_aux = batch['c_aux_warped'].cuda()
        c_torso = batch['c_torso_warped'].cuda()

        # Supervision
        # human_img = batch['human_img'].cuda()
        # human_parse_label = batch['human_parse_label'].cuda()
        # human_parse_masked_label = batch['human_parse_masked_label'].cuda()

        # print("c_torso.size() = {} [{}, {}]".format(c_torso.size(), torch.min(c_torso), torch.max(c_torso)))
        # print("c_aux.size() = {} [{}, {}]".format(c_aux.size(), torch.min(c_aux), torch.max(c_aux)))
        # print("human_parse_masked.size() = {} [{}, {}]".format(human_parse_masked.size(), torch.min(human_parse_masked), torch.max(human_parse_masked)))
        # print("human_masked.size() = {} [{}, {}]".format(human_masked.size(), torch.min(human_masked), torch.max(human_masked)))
        # print("human_pose.size() = {} [{}, {}]".format(human_pose.size(), torch.min(human_pose), torch.max(human_pose)))
        # exit()

        with torch.no_grad():
            c_img = torch.cat([c_torso, c_aux], dim=1)
            parsing_pred, parsing_pred_hard, tryon_img_fakes = model_pkl(c_img, human_parse_masked, human_masked, human_pose)
        fid_pred_folder = os.path.join(cotton_dir, "code/main/result/Top_1024x768_COTTON", mode, brand, "1")
        os.makedirs(fid_pred_folder, exist_ok=True)
        for idx, tryon_img_fake in enumerate(tryon_img_fakes):
            utils.imsave_trainProcess([utils.remap(tryon_img_fake)], os.path.join(fid_pred_folder, c_name[idx]))

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
    # os.chdir(preprocess_dir)
    from preprocessing.openpose_select import openpose_select_py
    from preprocessing.parse_select import parse_select_py
    from preprocessing.Self_Correction_Human_Parsing.simple_extractor_for_preprocessing import simple_extractor_for_preprocessing_py
    from preprocessing.mergeLabel import merge_label_py
    from preprocessing.build_data_gradio_demo import build_data_gradio_demo_py

    print(f"========= Find pose for {brand} =========")
    container_name = "openpose"
    command_to_run = f"bash find_pose.sh -b {brand}"
    try:
        client = docker.from_env()
        try:
            client.ping()
            print("Docker is running")
        except docker.errors.APIError as e:
            raise Exception("Docker is not running")
        
        try:
            container = client.containers.get(container_name)
            print(f"Container {container_name} exists")
        except docker.errors.NotFound as e:
            raise Exception(f"Container {container_name} does not exist")
        
        if container.status != "running":
            print(f"Container {container_name} is not running")
            try:
                container.start()
                time.sleep(3)
            except docker.errors.APIError as e:
                raise Exception(f"Error starting container {container_name}")
        
        try:
            exit_code, output = container.exec_run(
                cmd=command_to_run, 
                tty=True,
            )
            print(f"Result: {exit_code}, {output}")
            if exit_code != 0:
                raise Exception(f"Error running command {command_to_run}")
        except docker.errors.APIError as e:
            raise Exception(f"Error executing command {command_to_run}")
    except Exception as e:
        print(f"An error occurred: {e}")
        return
    
    print("========= Openpose Select =========")
    openpose_select_py(brand)

    print("========= CIHP Parsing =========")
    # os.chdir(os.path.join(preprocess_dir, "CIHP_PARSING"))
    # subprocess.run([
    #     "python", "human_parse.py",
    #     "--brand", brand
    # ], check=True)
    # os.chdir(preprocess_dir)
    # Execute CIHP Parsing
    in_cihp_parsing_path = os.path.join(Data_path, 'pose_filtered_Data', brand, 'VTON_Test_Gradio', 'model')
    out_cihp_parsing_path = os.path.join(Data_path, 'pose_filtered_Data', brand, 'VTON_Test_Gradio', 'CIHP')
    cihp_parsing_gen(in_cihp_parsing_path, out_cihp_parsing_path)

    print("========= Parse Select =========")
    parse_select_py(brand)

    print("========= ATR Generation and Parsing Merge =========")
    restore_model_atr = os.path.join(preprocess_dir, "Self_Correction_Human_Parsing/exp-schp-201908301523-atr.pth")
    simple_extractor_for_preprocessing_py("atr", restore_model_atr, brand)

    print("========= Merge Label =========")
    merge_label_py(brand)

    print("========= Build Data Gradio Demo =========")
    build_data_gradio_demo_py(brand, "p_model", 1024, 768)
    build_data_gradio_demo_py(brand, "train_val_split", 1024, 768)

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
    from preprocessing.U2Net.u2net_test import u2net_test_py
    from preprocessing.Sleeve_Classifier.main import sleeve_classifier_py
    from preprocessing.build_data_gradio_demo import build_data_gradio_demo_py
    from preprocessing.Cloth2Skeleton.main import cloth2skeleton_py
    from preprocessing.ClothSegmentation.main import clothsegmentation_py

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
    u2net_test_py(brand)

    print("========= Product Classification =========")
    sleeve_classifier_py("preprocess", brand)

    print("========= Build Data Gradio Demo =========")
    build_data_gradio_demo_py(brand, "p_product", 1024, 768)

    print("========= Cloth2Skeleton =========")
    config_cloth2skel = os.path.join(preprocess_dir, "Cloth2Skeleton/configs/config_bottom_v2_allData_augT.yaml")
    cloth2skeleton_py("test", config_cloth2skel, brand)

    print("========= ClothSegmentation =========")
    clothsegmentation_py("test", brand)

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
    global cotton_dir
    cotton_dir = os.path.dirname(os.path.dirname(script_dir))
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
    
    example_model_list.sort(key=lambda x: x[1])
    example_product_list.sort(key=lambda x: x[1])
    # Load model inference
    config_path = os.path.join(cotton_dir, "code", "main", "configs", "config_top_COTTON.yaml")
    global config
    config = yaml.load(open(config_path, "r"), Loader=yaml.FullLoader)
    config['TUCK'] = True
    config['VAL_CONFIG']['SCALE'] = 1
    config['VAL_CONFIG']['MASK_ARM'] = False
    global model_pkl
    model_pkl = COTTON(config).cuda().train()
    weight_path = os.path.join(cotton_dir, "code/main/result/Top_1024x768_COTTON/weights/Top_1024x768_COTTON_1.pkl")
    checkpoint = torch.load(weight_path, map_location='cpu')
    model_pkl.load_state_dict(checkpoint['state_dict'])
    model_pkl.cuda().eval()
    print("Model Inference loaded")

    # Load parsing model(CIHP Parsing)
    global FROZEN_MODEL_PATH
    FROZEN_MODEL_PATH = os.path.join(preprocess_dir, "CIHP_PARSING/checkpoint/CIHP_pgn/frozen_inference_graph_GPU.pb")
    global parsing_sess, parsing_graph, coord, threads
    parsing_sess, parsing_graph = parsing_init_()
    print("Parsing model loaded")

    kotaemon = gr.Theme.from_hub("lone17/kotaemon")
    with gr.Blocks(theme=kotaemon) as demo:
        gr.Markdown("# Virtual Try-on")
        
        with gr.Row():
            brand_input = gr.Textbox(label="Brand", placeholder="Input to brand", value="gradio_demo1")

        with gr.Row():
            with gr.Column():
                model_input = gr.Image(type="pil", label="Upload Model img")
                model_button = gr.Button("Preprocess Model", variant="secondary")
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
                product_button = gr.Button("Preprocess Product", variant="secondary")
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
                inference_button = gr.Button("Inference", variant="primary")
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

    demo.launch(share=False, server_name="127.0.0.1", server_port=7861) 

if __name__ == "__main__":
    main()