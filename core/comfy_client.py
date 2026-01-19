import json
import urllib.request
import urllib.parse
import random
import websocket
import sys
import os
from config import COMFYUI_SERVER_ADDRESS, CLIENT_ID, WORKFLOW_FILE, PONY_PREFIX

class ComfyClient:
    def __init__(self):
        self.server_address = COMFYUI_SERVER_ADDRESS
        self.client_id = CLIENT_ID
        # configから受け取ったパスをそのまま使う
        self.workflow_file = WORKFLOW_FILE

    def queue_prompt(self, prompt_workflow):
        p = {"prompt": prompt_workflow, "client_id": self.client_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request("http://{}/prompt".format(self.server_address), data=data)
        return json.loads(urllib.request.urlopen(req).read())

    def get_image(self, filename, subfolder, folder_type):
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(data)
        with urllib.request.urlopen("http://{}/view?{}".format(self.server_address, url_values)) as response:
            return response.read()

    def get_history(self, prompt_id):
        with urllib.request.urlopen("http://{}/history/{}".format(self.server_address, prompt_id)) as response:
            return json.loads(response.read())

    def get_images(self, ws, prompt_workflow):
        prompt_id = self.queue_prompt(prompt_workflow)['prompt_id']
        output_images = {}
        
        while True:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message['type'] == 'executing':
                    data = message['data']
                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        break # Execution complete
            else:
                continue

        history = self.get_history(prompt_id)[prompt_id]
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                images_output = []
                for image in node_output['images']:
                    image_data = self.get_image(image['filename'], image['subfolder'], image['type'])
                    images_output.append(image_data)
                output_images[node_id] = images_output
        return output_images

    def generate_image(self, prompt_text):
        """
        Generates an image via ComfyUI.
        Returns: Image bytes or None if failed.
        """
        try:
            print(f"[ComfyClient] Loading workflow from: {self.workflow_file}")
            
            if not os.path.exists(self.workflow_file):
                print(f"[ComfyClient] ERROR: Workflow file not found at {self.workflow_file}")
                return None

            with open(self.workflow_file, "r", encoding="utf-8") as f:
                prompt_data = json.load(f)
            
            # -------------------------------------------------
            # ★ 柔軟なNode探し (6番がダメなら他を探す！)
            # -------------------------------------------------
            target_node = None
            
            # パターンA: Node 6 (Pony V6など標準的)
            if "6" in prompt_data and "inputs" in prompt_data["6"] and "text" in prompt_data["6"]["inputs"]:
                target_node = "6"
            # パターンB: Node 26:7 (グループ化されたノードなど)
            elif "26:7" in prompt_data and "inputs" in prompt_data["26:7"] and "text" in prompt_data["26:7"]["inputs"]:
                target_node = "26:7"
            # パターンC: Node 7 (CLIP Text Encodeの予備)
            elif "7" in prompt_data and "inputs" in prompt_data["7"] and "text" in prompt_data["7"]["inputs"]:
                target_node = "7"

            if target_node:
                # Prompt入力
                print(f"[ComfyClient] Injecting prompt into Node {target_node}")
                prompt_data[target_node]["inputs"]["text"] = PONY_PREFIX + prompt_text
            else:
                print("[ComfyClient] ERROR: No suitable text input node found (Checked 6, 26:7, 7)")
                return None

            # -------------------------------------------------
            # ★ Seedのランダム化 (Node 3)
            # -------------------------------------------------
            if "3" in prompt_data and "inputs" in prompt_data["3"] and "seed" in prompt_data["3"]["inputs"]:
                prompt_data["3"]["inputs"]["seed"] = random.randint(1, 1000000000000)
            else:
                print("[ComfyClient] WARNING: Seed node (3) not found. Image will be static.")

            # Websocket Connection
            ws = websocket.WebSocket()
            ws.connect("ws://{}/ws?clientId={}".format(self.server_address, self.client_id))
            
            images = self.get_images(ws, prompt_data)
            
            # Return the first image found
            for node_id in images:
                for image_data in images[node_id]:
                    return image_data
            
            return None

        except Exception as e:
            print(f"[ComfyClient] CRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc()
            return None