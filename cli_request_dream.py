import requests, json, os, time, argparse, base64
import yaml
import sys

from cli_logger import logger, set_logger_verbosity, quiesce_logger, test_logger
from PIL import Image
from io import BytesIO
from requests.exceptions import ConnectionError

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument(
    "-n",
    "--amount",
    action="store",
    required=False,
    type=int,
    help="The amount of images to generate with this prompt",
)
arg_parser.add_argument(
    "-p",
    "--prompt",
    action="store",
    required=False,
    type=str,
    help="The prompt with which to generate images",
)
arg_parser.add_argument(
    "-w",
    "--width",
    action="store",
    required=False,
    type=int,
    help="The width of the image to generate. Has to be a multiple of 64",
)
arg_parser.add_argument(
    "-l",
    "--height",
    action="store",
    required=False,
    type=int,
    help="The height of the image to generate. Has to be a multiple of 64",
)
arg_parser.add_argument(
    "-s",
    "--steps",
    action="store",
    required=False,
    type=int,
    help="The amount of steps to use for this generation",
)
arg_parser.add_argument(
    "--api_key",
    type=str,
    action="store",
    required=False,
    help="The API Key to use to authenticate on the Horde. Get one in https://aihorde.net/register",
)
arg_parser.add_argument(
    "-f",
    "--filename",
    type=str,
    action="store",
    required=False,
    help="The filename to use to save the images. If more than 1 image is generated, the number of generation will be prepended",
)
arg_parser.add_argument(
    "-v",
    "--verbosity",
    action="count",
    default=0,
    help="The default logging level is ERROR or higher. This value increases the amount of logging seen in your screen",
)
arg_parser.add_argument(
    "-q",
    "--quiet",
    action="count",
    default=0,
    help="The default logging level is ERROR or higher. This value decreases the amount of logging seen in your screen",
)
arg_parser.add_argument(
    "--horde",
    action="store",
    required=False,
    type=str,
    default="https://dev.aihorde.net",
    help="Use a different horde",
)
arg_parser.add_argument(
    "--nsfw",
    action="store_true",
    default=False,
    required=False,
    help="Mark the request as NSFW. Only servers which allow NSFW will pick it up",
)
arg_parser.add_argument(
    "--censor_nsfw",
    action="store_true",
    default=False,
    required=False,
    help="If the request is SFW, and the worker accidentaly generates NSFW, it will send back a censored image.",
)
arg_parser.add_argument(
    "--trusted_workers",
    action="store_true",
    default=False,
    required=False,
    help="If true, the request will be sent only to trusted workers.",
)
arg_parser.add_argument(
    "--source_image",
    action="store",
    required=False,
    type=str,
    help="When a file path is provided, will be used as the source for img2img",
)
arg_parser.add_argument(
    "--source_processing",
    action="store",
    required=False,
    type=str,
    help="Can either be img2img, inpainting, or outpainting",
)
arg_parser.add_argument(
    "--source_mask",
    action="store",
    required=False,
    type=str,
    help="When a file path is provided, will be used as the mask source for inpainting/outpainting",
)
args = arg_parser.parse_args()


class RequestData(object):
    def __init__(self):
        self.client_agent = "cli_request_dream.py:1.0.0:(discord)db0#1625"
        self.api_key = "000000000"
        self.filename = "horde_dream.png"
        self.imgen_params = {
            "n": 1,
            "width": 64 * 8,
            "height": 64 * 8,
            "steps": 20,
            "sampler_name": "k_euler_a",
            "cfg_scale": 7.5,
            "denoising_strength": 0.6,
        }
        self.submit_dict = {
            "prompt": "a horde of cute stable robots in a sprawling server room repairing a massive mainframe",
            "nsfw": False,
            "censor_nsfw": False,
            "trusted_workers": False,
            "models": ["stable_diffusion"],
            "r2": True,
            "dry_run": True,
        }
        self.source_image = None
        self.source_processing = "img2img"
        self.source_mask = None

    def get_submit_dict(self):
        submit_dict = self.submit_dict.copy()
        submit_dict["params"] = self.imgen_params
        submit_dict["source_processing"] = self.source_processing
        if self.source_image:
            final_src_img = Image.open(self.source_image)
            buffer = BytesIO()
            # We send as WebP to avoid using all the horde bandwidth
            final_src_img.save(buffer, format="Webp", quality=95, exact=True)
            submit_dict["source_image"] = base64.b64encode(buffer.getvalue()).decode(
                "utf8"
            )
        if self.source_mask:
            final_src_mask = Image.open(self.source_mask)
            buffer = BytesIO()
            # We send as WebP to avoid using all the horde bandwidth
            final_src_mask.save(buffer, format="Webp", quality=95, exact=True)
            submit_dict["source_mask"] = base64.b64encode(buffer.getvalue()).decode(
                "utf8"
            )
        return submit_dict


def load_request_data():
    request_data = RequestData()
    if os.path.exists("cliRequestsData_Dream.yml"):
        with open(
            "cliRequestsData_Dream.yml", "rt", encoding="utf-8", errors="ignore"
        ) as configfile:
            config = yaml.safe_load(configfile)
            for key, value in config.items():
                setattr(request_data, key, value)
    if args.api_key:
        request_data.api_key = args.api_key
    if args.filename:
        request_data.filename = args.filename
    if args.amount:
        request_data.imgen_params["n"] = args.amount
    if args.width:
        request_data.imgen_params["width"] = args.width
    if args.height:
        request_data.imgen_params["height"] = args.height
    if args.steps:
        request_data.imgen_params["steps"] = args.steps
    if args.prompt:
        request_data.submit_dict["prompt"] = args.prompt
    if args.nsfw:
        request_data.submit_dict["nsfw"] = args.nsfw
    if args.censor_nsfw:
        request_data.submit_dict["censor_nsfw"] = args.censor_nsfw
    if args.trusted_workers:
        request_data.submit_dict["trusted_workers"] = args.trusted_workers
    if args.source_image:
        request_data.source_image = args.source_image
    if args.source_processing:
        request_data.source_processing = args.source_processing
    if args.source_mask:
        request_data.source_mask = args.source_mask
    return request_data


@logger.catch(reraise=True)
def generate(request_data):
    # final_submit_dict["source_image"] = 'Test'
    headers = {
        "apikey": request_data.api_key,
        "Client-Agent": request_data.client_agent,
    }
    # logger.debug(request_data.get_submit_dict())
    submit_req = requests.post(
        f"{args.horde}/api/v2/generate/async",
        json=request_data.get_submit_dict(),
        headers=headers,
    )
    if submit_req.ok:
        submit_results = submit_req.json()
        try:
            req_id = submit_results["id"]
        except KeyError:
            # logger.warning("Dry run detected, no request ID returned. Exiting.")
            return submit_results["kudos"]
        logger.debug(submit_results)

        is_done = False
        retry = 0
        cancelled = False
        try:
            while not is_done:
                try:
                    chk_req = requests.get(
                        f"{args.horde}/api/v2/generate/check/{req_id}"
                    )
                    if not chk_req.ok:
                        logger.error(chk_req.text)
                        return
                    chk_results = chk_req.json()
                    logger.info(chk_results)
                    is_done = chk_results["done"]
                    time.sleep(0.8)
                except ConnectionError as e:
                    retry += 1
                    logger.error(f"Error {e} when retrieving status. Retry {retry}/10")
                    if retry < 10:
                        time.sleep(1)
                        continue
                    raise
        except KeyboardInterrupt:
            logger.info(f"Cancelling {req_id}...")
            cancelled = True
            retrieve_req = requests.delete(
                f"{args.horde}/api/v2/generate/status/{req_id}"
            )
        if not cancelled:
            retrieve_req = requests.get(f"{args.horde}/api/v2/generate/status/{req_id}")
        if not retrieve_req.ok:
            logger.error(retrieve_req.text)
            return
        results_json = retrieve_req.json()
        # logger.debug(results_json)
        if results_json["faulted"]:
            final_submit_dict = request_data.get_submit_dict()
            if "source_image" in final_submit_dict:
                final_submit_dict[
                    "source_image"
                ] = f"img2img request with size: {len(final_submit_dict['source_image'])}"
            logger.error(
                f"Something went wrong when generating the request. Please contact the horde administrator with your request details: {final_submit_dict}"
            )
            return
        results = results_json["generations"]
        for iter in range(len(results)):
            final_filename = request_data.filename
            if len(results) > 1:
                final_filename = f"{iter}_{request_data.filename}"
            if request_data.get_submit_dict()["r2"]:
                logger.debug(
                    f"Downloading '{results[iter]['id']}' from {results[iter]['img']}"
                )
                try:
                    img_data = requests.get(results[iter]["img"]).content
                except:
                    logger.error("Received b64 again")
                with open(final_filename, "wb") as handler:
                    handler.write(img_data)
            else:
                b64img = results[iter]["img"]
                base64_bytes = b64img.encode("utf-8")
                img_bytes = base64.b64decode(base64_bytes)
                img = Image.open(BytesIO(img_bytes))
                img.save(final_filename)
            censored = ""
            if results[iter]["censored"]:
                censored = " (censored)"
            logger.generation(f"Saved{censored} {final_filename}")
    else:
        logger.error(submit_req.text)


set_logger_verbosity(5)
quiesce_logger(0)

all_tests = {
    "high_control_strength_no_denoise": {
        "control_strength": 1.0,
        "denoising_strength": None,
    },
    "low_control_strength_no_denoise": {
        "control_strength": 0.1,
        "denoising_strength": None,
    },
    "no_control_strength_high_denoise": {
        "control_strength": None,
        "denoising_strength": 1.0,
    },
    "no_control_strength_low_denoise": {
        "control_strength": None,
        "denoising_strength": 0.1,
    },
    "low_control_strength_and_low_denoise": {
        "control_strength": 0.1,
        "denoising_strength": 0.1,
    },
    "low_control_strength_and_high_denoise": {
        "control_strength": 0.1,
        "denoising_strength": 1,
    },
    "high_control_strength_and_low_denoise": {
        "control_strength": 1,
        "denoising_strength": 0.1,
    },
}

img2img_test_set = {
    "with_source_image": {
        "source_image": "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"
    },
    "without_source_image": {"source_image": None},
}


for test_name, test_params in all_tests.items():
    logger.warning(f"test: {test_name}")
    for img_param_name, img_param_value in img2img_test_set.items():
        request_data = load_request_data()
        request_data.imgen_params[img_param_name] = img_param_value

        for param_name, param_value in test_params.items():
            if param_value is not None:
                request_data.imgen_params[param_name] = param_value
            else:
                request_data.imgen_params.pop(param_name, None)

            logger.info(f"subtest: [{img_param_name}] {param_name}")
            kudos_without_control_type = generate(request_data)

            request_data.imgen_params["control_type"] = "canny"
            kudos_with_control_type = generate(request_data)
            request_data.imgen_params.pop("control_type", None)

            logger.info(f"with control_type:    {kudos_with_control_type}")
            logger.info(f"without control_type: {kudos_without_control_type}")

    print("-" * 80)
