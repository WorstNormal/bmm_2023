import datetime
import traci
from sumolib import checkBinary
import os
import xml.etree.ElementTree as ET
import sys
import shutil

ROOT_GENERATION_FILE = "network.net.xml"
CONFIG_FILE = "config.sumocfg"

GENERATION_DIRECTORY = os.path.abspath("gen")
INPUT_DIRECTORY = os.path.abspath("input")
OUTPUT_DIRECTORY = os.path.abspath("output")

N_EPOCHS = 10

ITERATION_STEPS = 500

TRAFFIC_LIGHTS_IDS = [
	"252613870", "J1", "892206755", "910721724", "910721948", "670132832", "670132830", "892761768", "892761473",
	"252613882", "575932021", "703059905", "702392925", "670132834", "1001684671", "1001684656", "583022051",
	"892206648", "655282392", "5617269297", "286639353", "J3", "892206624", "252613876", "670132800",
	"892206489", "910721898", "892206597"
]

TL_NUMBER = len(TRAFFIC_LIGHTS_IDS)

DELTA = 1

MSE_result = []
kph_result = []


open(os.path.join(OUTPUT_DIRECTORY, "mse.txt"), "w").close()
open(os.path.join(OUTPUT_DIRECTORY, "kph.txt"), "w").close()

MSE_out_file = open(os.path.join(OUTPUT_DIRECTORY, "mse.txt"), "a")
kph_out_file = open(os.path.join(OUTPUT_DIRECTORY, "kph.txt"), "a")

def clear_directory(directory: str) -> None:
	for f in os.listdir(directory):
		os.remove(os.path.join(directory, f))


def clear_directory_except(directory: str, *exceptions: str) -> None:
	for f in os.listdir(directory):
		if os.path.join(directory, f) in exceptions:
			continue
		os.remove(os.path.join(directory, f))

def generate_xmls(generation_directory: str, base_file: str, tl_id: str, delta: int) -> None:
	tree = ET.parse(base_file)
	root = tree.getroot()
	result = list()
	for tlLog in root.iter("tlLogic"):
		if tlLog.items()[0][1] == tl_id:
			need_to_update = []
			counter = 0
			for i in range(len(tlLog)):
				if not('y' in tlLog[i].items()[1][1]):
					counter += 1
					need_to_update.append(i)
			if counter == 1:
				x = int(tlLog[need_to_update[0]].items()[0][1])
				for x1 in range(max(x - delta, 1), x + 1 + delta):
					tlLog[need_to_update[0]].attrib['duration'] = str(x1)
					filename = os.path.join(
						generation_directory,
						f"{tl_id}_{x1}-{need_to_update[0]}.net.xml"
					)
					tree.write(filename)
					result.append(filename)
			elif counter == 2:
				x = int(tlLog[need_to_update[0]].items()[0][1])
				y = int(tlLog[need_to_update[1]].items()[0][1])
				for x1 in range(max(x - delta, 1), x + 1 + delta):
					for x2 in range(max(y - delta, 1), y + 1 + delta):
						tlLog[need_to_update[0]].attrib['duration'] = str(x1)
						tlLog[need_to_update[1]].attrib['duration'] = str(x2)
						filename = os.path.join(
							generation_directory,
							f"{tl_id}_{x1}-{need_to_update[0]}_{x2}-{need_to_update[1]}.net.xml"
						)
						tree.write(filename)
						result.append(filename)
			elif counter == 3:
				x = int(tlLog[need_to_update[0]].items()[0][1])
				y = int(tlLog[need_to_update[1]].items()[0][1])
				z = int(tlLog[need_to_update[2]].items()[0][1])
				for x1 in range(max(x - delta, 1), x + 1 + delta):
					for x2 in range(max(y - delta, 1), y + 1 + delta):
						for x3 in range(max(1, z - delta), z + 1 + delta):
							tlLog[need_to_update[0]].attrib['duration'] = str(x1)
							tlLog[need_to_update[1]].attrib['duration'] = str(x2)
							tlLog[need_to_update[2]].attrib['duration'] = str(x3)
							filename = os.path.join(
								generation_directory,
								f"{tl_id}_{x1}-{need_to_update[0]}_{x2}-{need_to_update[1]}_{x3}-{need_to_update[2]}.net.xml"
							)
							tree.write(filename)
							result.append(filename)
	return result

def edit_config(new_launch_file: str) -> None:
	tree = ET.parse(os.path.join(INPUT_DIRECTORY, CONFIG_FILE))
	root = tree.getroot()

	root[0][0].set("value", new_launch_file)
	tree.write(os.path.join(INPUT_DIRECTORY, CONFIG_FILE))

def create_summary_file(epoch_number: int, tl_reg: str) -> str:
	filename = os.path.join(OUTPUT_DIRECTORY, "summary_{}_{}.xml".format(epoch_number, tl_reg))
	open(os.path.join(OUTPUT_DIRECTORY, filename), "w").close()
	return filename

def calculate_MSE() -> float:
	MSE = 0

	vehicle_count = 0
	for vehicle_id in traci.vehicle.getIDList():
		vehicle_lane = traci.vehicle.getLaneID(vehicle_id)
		lane_max_speed = float(traci.lane.getMaxSpeed(vehicle_lane))
		vehicle_speed = traci.vehicle.getSpeed(vehicle_id)

		MSE += (lane_max_speed - vehicle_speed) ** 2
		vehicle_count += 1


	MSE = MSE if vehicle_count == 0 else MSE / vehicle_count

	return MSE

def get_kph(summary_file_path: str) -> float:
	tree = ET.parse(summary_file_path)
	root = tree.getroot()

	kph = 0
	for step in root:
		kph += float(step.attrib["meanSpeed"])

	kph /= ITERATION_STEPS

	return kph

def iteration(epoch_number: int, iteration_number: int, tl_id: str, prev_iteration_best_network_file: str) -> str:
	clear_directory_except(GENERATION_DIRECTORY, prev_iteration_best_network_file)

	print("[INFO | {}/{} | {:02d}/{:02d}(---/---)] Generating files for \"{}\"".format(epoch_number + 1, N_EPOCHS, iteration_number + 1, TL_NUMBER, prev_iteration_best_network_file))
	generated_files = generate_xmls(GENERATION_DIRECTORY, prev_iteration_best_network_file, tl_id, DELTA)
	print("[INFO | {}/{} | {:02d}/{:02d}(---/---)] Generated files ({}): \n\t".format(epoch_number + 1, N_EPOCHS, iteration_number + 1, TL_NUMBER, len(generated_files)) + "\n\t".join(generated_files))
	print("[INFO | {}/{} | {:02d}/{:02d}(---/---)] Done generating!".format(epoch_number + 1, N_EPOCHS, iteration_number + 1, TL_NUMBER,))
	
	min_MSE_MSE = 1000000
	max_kph = -1

	iteration_best_network_file = prev_iteration_best_network_file
	prev_launch_file = prev_iteration_best_network_file
	for file_idx, generated_file in enumerate(generated_files):
		print("[INFO | {}/{} | {:02d}/{:02d}({:03d}/{:03d})] Editing config: setting netfile to \"{}\"".format(epoch_number + 1, N_EPOCHS, iteration_number + 1, TL_NUMBER, file_idx + 1, len(generated_files), generated_file))
		edit_config(generated_file)
		print("[INFO | {}/{} | {:02d}/{:02d}({:03d}/{:03d})] Done replacing!".format(epoch_number + 1, N_EPOCHS, iteration_number + 1, TL_NUMBER, file_idx + 1, len(generated_files)))

		print("[INFO | {}/{} | {:02d}/{:02d}({:03d}/{:03d})] Creating summary file for epoch={}, tl={}".format(epoch_number + 1, N_EPOCHS, iteration_number + 1, TL_NUMBER, file_idx + 1, len(generated_files), epoch_number + 1, tl_id))
		summary_file = create_summary_file(epoch_number + 1, os.path.relpath(generated_file, GENERATION_DIRECTORY)[:-8])
		print("[INFO | {}/{} | {:02d}/{:02d}({:03d}/{:03d})] Summary file with name \"{}\" created".format(epoch_number + 1, N_EPOCHS, iteration_number + 1, TL_NUMBER, file_idx + 1, len(generated_files), summary_file))

		print("[INFO | {}/{} | {:02d}/{:02d}({:03d}/{:03d})] Starting SUMO".format(epoch_number + 1, N_EPOCHS, iteration_number + 1, TL_NUMBER, file_idx + 1, len(generated_files)))
		sumo_binary = checkBinary('sumo')
		sumo_cmd = [sumo_binary,
			"-c", os.path.join(INPUT_DIRECTORY, CONFIG_FILE),
			"--summary", summary_file,
			"--precision", "6",
			"-W", "true"
		]
		traci.start(sumo_cmd)

		MSE_MSE = 0

		step = 0
		while step < ITERATION_STEPS:
			traci.simulationStep()
			MSE = calculate_MSE()
			MSE_MSE += MSE ** 2
			step += 1

		traci.close()
		print("[INFO | {}/{} | {:02d}/{:02d}({:03d}/{:03d})] Closed SUMO".format(epoch_number + 1, N_EPOCHS, iteration_number + 1, TL_NUMBER, file_idx + 1, len(generated_files)))

		MSE_MSE /= ITERATION_STEPS
		kph = get_kph(summary_file)

		if MSE_MSE < min_MSE_MSE:
			max_kph = kph
			min_MSE_MSE = MSE_MSE
			iteration_best_network_file = generated_file
		elif MSE_MSE == min_MSE_MSE:
			if kph > max_kph:
				max_kph = kph
				min_MSE_MSE = MSE_MSE
				iteration_best_network_file = generated_file

		prev_launch_file = generated_file


		MSE_out_file.write(str(MSE_MSE) + "\n")
		kph_out_file.write(str(kph) + "\n")

	return iteration_best_network_file

def epoch(epoch_number: int, prev_epoch_best_network_file: str) -> str:
	prev_iteration_best_network_file = prev_epoch_best_network_file
	for iteration_number, tl_id in enumerate(TRAFFIC_LIGHTS_IDS):
		iteration_best_network_file = iteration(epoch_number, iteration_number, tl_id, prev_iteration_best_network_file)
		print("[INFO | {}/{} | {:02d}/{:02d}(---/---)] Best on iteration is \"{}\"".format(epoch_number + 1, N_EPOCHS, iteration_number + 1, TL_NUMBER, iteration_best_network_file))
		print("[INFO | {}/{} | {:02d}/{:02d}(---/---)] Renaming best file...".format(epoch_number + 1, N_EPOCHS, iteration_number + 1, TL_NUMBER))
		os.replace(iteration_best_network_file, os.path.join(GENERATION_DIRECTORY, "best.xml"))
		print("[INFO | {}/{} | {:02d}/{:02d}(---/---)] Renamed".format(epoch_number + 1, N_EPOCHS, iteration_number + 1, TL_NUMBER))
		prev_iteration_best_network_file = os.path.join(GENERATION_DIRECTORY, "best.xml")
	return prev_iteration_best_network_file

def main() -> int:
	if "SUMO_HOME" in os.environ:
		tools = os.path.join(os.environ["SUMO_HOME"], "tools")
		sys.path.append(tools)
	else:
		sys.exit("Please declare enviroment variable \"SUMO_HOME\"")

	clear_directory(GENERATION_DIRECTORY)
	clear_directory_except(OUTPUT_DIRECTORY, os.path.join(OUTPUT_DIRECTORY, "mse.txt"), os.path.join(OUTPUT_DIRECTORY, "kph.txt"))

	prev_epoch_best_network_file = os.path.join(INPUT_DIRECTORY, ROOT_GENERATION_FILE)

	for epoch_number in range(N_EPOCHS):
		print("="*45 + " EPOCH {} ".format(epoch_number + 1) + "="*45)
		epoch_best_network_file = epoch(epoch_number, prev_epoch_best_network_file)
		print("[INFO | {}/{} | --/--(---/---)] Best on epoch is \"{}\"".format(epoch_number + 1, N_EPOCHS, epoch_best_network_file))
		prev_epoch_best_network_file = epoch_best_network_file

	print("="*43 + " END EPOCHS " + "="*43)

	return 0

main()