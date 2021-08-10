import os
import sys
import pickle
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import tensorflow as tf
from selfies import decoder
from .Network import helper

os.environ["CUDA_VISIBLE_DEVICES"] = "0"
gpus = tf.config.experimental.list_physical_devices('GPU')
for gpu in gpus:
	tf.config.experimental.set_memory_growth(gpu, True)

"""
   DECIMER to incorporate into python programs.

   Translates a image with a chemical structure to SMILES.

   The DECIMER 1.0 (Deep lEarning for Chemical ImagE Recognition) project was launched to address the OCSR problem with the latest computational intelligence methods to provide an automated open-source software solution.

   For easy usage refer to DECIMER_V1.0 commandline python script.
   Note: The default model is set to predict Canonical SMILES. 

   Avilable models:
   ================
   - Canonical : Model trained on images depicted using canonical SMILES (without stereochemistry).
   - Isomeric : Model trained on images depicted using isomeric SMILES (with stereochemistry).
   - Augmented: Model trained on images depicted using isomeric SMILES with augmentations.

"""
def load_trained_model(model_id):
	"""This functions loads the trained models and the pickle files.
	   
	   If the models are not present on the desired location the functions will automatically download the models.
	   :param model_id: The model which is desired by the user.
	   :return: EfficientNet weights to extract the image features from an image, Transformer model, maximum length of the SELFIES string and SELFIES tokenizer.

	"""
	SELFIES_tokenizer, max_length = helper.load_assets(model_id)
	if model_id == "Canonical":
		vocabulary = "max_length"
		get_type = max_length
	else:
		vocabulary = "SELFIES_tokenizer"
		get_type = SELFIES_tokenizer
	transformer, target_size = helper.load_transformer(vocabulary, get_type)
	image_features_extracter = helper.load_image_features_extract_model(target_size)

	# restoring the latest checkpoint in checkpoint_dir
	checkpoint_path = 'Trained_Models/' + model_id + '/'
	model_url = 'https://storage.googleapis.com/iupac_models_trained/DECIMER_transformer_models/DECIMER_trained_models_v1.0.zip'
	if not os.path.exists(checkpoint_path):
		helper.download_trained_weights(model_url, checkpoint_path)

	optimizer = tf.keras.optimizers.Adam(learning_rate=0.00051)

	ckpt = tf.train.Checkpoint(transformer=transformer, optimizer=optimizer)
	ckpt.restore(tf.train.latest_checkpoint(checkpoint_path)).expect_partial()

	return image_features_extracter, transformer, max_length, SELFIES_tokenizer 

# Evaluator
def evaluate(image,image_features_extracter, transformer, max_length, SELFIES_tokenizer):
	"""
		This function is the main function of this class.

		This function converts the image into a feature vector and feeds the feature vector to the transformer model.
		The transformer then goes through the feature vector while tries to predict the SELFIES tokens one by one until the desired SELFIES string is generated or until the maximum length is reached.
		
		:param image: Path of the image file.
		:return: Predicted SELFIES string for each image file.


	"""
	temp_input = tf.expand_dims(helper.load_image(image)[0], 0)
	img_tensor_val = image_features_extracter(temp_input)
	img_tensor_val = tf.reshape(img_tensor_val, (img_tensor_val.shape[0], -1, img_tensor_val.shape[3]))

	output = tf.expand_dims([SELFIES_tokenizer.word_index['<start>']], 0)
	result = []
	end_token = SELFIES_tokenizer.word_index['<end>']

	for i in range(max_length):
		dec_mask = helper.create_masks_decoder(output)

		predictions, _ = transformer(img_tensor_val, output, False, dec_mask)
		predictions = predictions[:, -1:, :]
		predicted_id = tf.cast(tf.argmax(predictions, axis=-1), tf.int32)

		if predicted_id == end_token:
			return result

		result.append(SELFIES_tokenizer.index_word[int(predicted_id)])
		output = tf.concat([output, predicted_id], axis=-1)

	return result

	# Predictor helper function
def predict_SMILES(image_path,model_id = "Canonical"):
	"""
		This function enables the user to parse an Image to the evaluator function.
		And decodes the SELFIES string generated by the evaluator function.

		:param image_path:	Path of the image in the local storage.
		:return: SMILES string decoded from the predicted SELFIES.
	"""
	image_features_extracter, transformer, max_length, SELFIES_tokenizer = load_trained_model(model_id)
	
	predicted_SELFIES = evaluate(image_path,image_features_extracter, transformer, max_length, SELFIES_tokenizer)

	predicted_SMILES = decoder(''.join(predicted_SELFIES).replace("<start>", "").replace("<end>", ""),
							   constraints='hypervalent')

	return predicted_SMILES