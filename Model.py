import numpy as np
import tensorflow as tf
import os

tf.compat.v1.disable_eager_execution()
'''
Handwritten text recognition model written by Harald Scheidl:
https://github.com/githubharald/SimpleHTR
'''

class DecoderType:
    BestPath = 0
    WordBeamSearch = 1


class Model:
    # model constants
    batchSize = 50
    imgSize = (128, 32)
    maxTextLen = 32

    def __init__(self, charList, decoderType=DecoderType.BestPath,
                 mustRestore=False, dump=False):
        tf.compat.v1.reset_default_graph()
        self.dump = dump
        self.charList = charList
        self.decoderType = decoderType
        self.mustRestore = mustRestore
        self.snapID = 0

        # Whether to use normalization over a batch or a population
        self.is_train = tf.compat.v1.placeholder(tf.bool, name='is_train')

        # input image batch
        self.inputImgs = tf.compat.v1.placeholder(tf.float32, shape=(
        None, Model.imgSize[0], Model.imgSize[1]))

        # setup CNN, RNN and CTC
        self.setupCNN()
        self.setupRNN()
        self.setupCTC()

        # setup optimizer to train NN
        self.batchesTrained = 0
        self.learningRate = tf.compat.v1.placeholder(tf.float32, shape=[])
        self.update_ops = tf.compat.v1.get_collection(tf.compat.v1.GraphKeys.UPDATE_OPS)
        with tf.control_dependencies(self.update_ops):
            self.optimizer = tf.compat.v1.train.RMSPropOptimizer(
                self.learningRate).minimize(self.loss)

        # initialize TF
        (self.sess, self.saver) = self.setupTF()

    def setupCNN(self):
        cnnIn4d = tf.expand_dims(input=self.inputImgs, axis=3)

        # list of parameters for the layers
        kernelVals = [5, 5, 3, 3, 3]
        featureVals = [1, 32, 64, 128, 128, 256]
        strideVals = poolVals = [(2, 2), (2, 2), (1, 2), (1, 2), (1, 2)]
        numLayers = len(strideVals)

        # create layers
        pool = cnnIn4d  # input to first CNN layer
        for i in range(numLayers):
            kernel = tf.Variable(tf.random.truncated_normal(
                [kernelVals[i], kernelVals[i], featureVals[i],
                 featureVals[i + 1]], stddev=0.1))
            conv = tf.nn.conv2d(input=pool, filters=kernel, padding='SAME',
                                strides=(1, 1, 1, 1))
            conv_norm = tf.compat.v1.layers.batch_normalization(conv,
                                                      training=self.is_train)
            relu = tf.nn.relu(conv_norm)
            pool = tf.nn.max_pool2d(input=relu, ksize=(1, poolVals[i][0], poolVals[i][1], 1),
                                  strides=(1, strideVals[i][0], strideVals[i][1], 1),
                                  padding='VALID')

        self.cnnOut4d = pool

    def setupRNN(self):
        rnnIn3d = tf.squeeze(self.cnnOut4d, axis=[2])

        # basic cells which is used to build RNN
        numHidden = 256
        cells = [
            tf.compat.v1.nn.rnn_cell.LSTMCell(num_units=numHidden, state_is_tuple=True)
            for _ in range(2)]  # 2 layers

        # stack basic cells
        stacked = tf.compat.v1.nn.rnn_cell.MultiRNNCell(cells, state_is_tuple=True)

        # bidirectional RNN
        # BxTxF -> BxTx2H
        ((fw, bw), _) = tf.compat.v1.nn.bidirectional_dynamic_rnn(cell_fw=stacked,
                                                        cell_bw=stacked,
                                                        inputs=rnnIn3d,
                                                        dtype=rnnIn3d.dtype)

        # BxTxH + BxTxH -> BxTx2H -> BxTx1X2H
        concat = tf.expand_dims(tf.concat([fw, bw], 2), 2)

        # project output to chars (including blank): BxTx1x2H -> BxTx1xC -> BxTxC
        kernel = tf.Variable(
            tf.random.truncated_normal([1, 1, numHidden * 2, len(self.charList) + 1],
                                stddev=0.1))
        self.rnnOut3d = tf.squeeze(
            tf.nn.atrous_conv2d(value=concat, filters=kernel, rate=1,
                                padding='SAME'), axis=[2])

    def setupCTC(self):
        # BxTxC -> TxBxC
        self.ctcIn3dTBC = tf.transpose(a=self.rnnOut3d, perm=[1, 0, 2])
        # ground truth text as sparse tensor
        self.gtTexts = tf.SparseTensor(
            tf.compat.v1.placeholder(tf.int64, shape=[None, 2]),
            tf.compat.v1.placeholder(tf.int32, [None]), tf.compat.v1.placeholder(tf.int64, [2]))

        # calc loss for batch
        self.seqLen = tf.compat.v1.placeholder(tf.int32, [None])
        self.loss = tf.reduce_mean(
            input_tensor=tf.compat.v1.nn.ctc_loss(labels=self.gtTexts, inputs=self.ctcIn3dTBC,
                           sequence_length=self.seqLen,
                           ctc_merge_repeated=True))

        # calc loss for each element to compute label probability
        self.savedCtcInput = tf.compat.v1.placeholder(tf.float32,
                                            shape=[Model.maxTextLen, None,
                                                   len(self.charList) + 1])
        self.lossPerElement = tf.compat.v1.nn.ctc_loss(labels=self.gtTexts,
                                             inputs=self.savedCtcInput,
                                             sequence_length=self.seqLen,
                                             ctc_merge_repeated=True)

        # decoder: either best path decoding or beam search decoding
        if self.decoderType == DecoderType.BestPath:
            self.decoder = tf.nn.ctc_greedy_decoder(inputs=self.ctcIn3dTBC,
                                                    sequence_length=self.seqLen)
        elif self.decoderType == DecoderType.WordBeamSearch:
            # import compiled word beam search operation (see https://github.com/githubharald/CTCWordBeamSearch)
            # Get the path of the current script
            script_path = os.path.abspath(__file__)
            
            # Get the directory containing the script
            script_directory = os.path.dirname(script_path)
            
            # Construct the path to the TFWordBeamSearch.so file
            so_file_path = os.path.join(script_directory, 'TFWordBeamSearch.so')
            
            isFile = os.path.isfile(so_file_path)

            print(isFile)
            print(so_file_path)

            word_beam_search_module = tf.load_op_library(so_file_path)

            # prepare information about language (dictionary, characters in dataset, characters forming words)
            chars = str().join(self.charList)

            with open('model/wordCharList.txt', "rb") as f:
                byte = f.read(1)
                if byte != "":
                    byte = f.read()
                    myString = byte.decode("Windows-1255")
                    wordChars = myString.splitlines()[0]


            corpus = open('data/corpus.txt').read()

            # decode using the "Words" mode of word beam search
            self.decoder = word_beam_search_module.word_beam_search(
                tf.nn.softmax(self.ctcIn3dTBC, axis=2), 50, 'Words', 0.0,
                corpus.encode('utf8'), chars.encode('utf8'),
                wordChars.encode('utf8'))

    def setupTF(self):
        sess = tf.compat.v1.Session()  # TF session

        saver = tf.compat.v1.train.Saver(max_to_keep=1)  # saver saves model to file
        modelDir = 'model/'
        latestSnapshot = tf.train.latest_checkpoint(
            modelDir)  # is there a saved model?

        # if model must be restored (for inference), there must be a snapshot
        if self.mustRestore and not latestSnapshot:
            raise Exception('No saved model found in: ' + modelDir)

        # load saved model if available
        if latestSnapshot:
            saver.restore(sess, latestSnapshot)
        else:
            sess.run(tf.compat.v1.global_variables_initializer())

        return (sess, saver)

    def toSparse(self, texts):
        indices = []
        values = []
        shape = [len(texts), 0]  # last entry must be max(labelList[i])

        # go over all texts
        for (batchElement, text) in enumerate(texts):
            # convert to string of label (i.e. class-ids)
            labelStr = [self.charList.index(c) for c in text]
            # sparse tensor must have size of max. label-string
            if len(labelStr) > shape[1]:
                shape[1] = len(labelStr)
            # put each label into sparse tensor
            for (i, label) in enumerate(labelStr):
                indices.append([batchElement, i])
                values.append(label)

        return (indices, values, shape)

    def decoderOutputToText(self, ctcOutput, batchSize):
        # contains string of labels for each batch element
        encodedLabelStrs = [[] for i in range(batchSize)]

        # word beam search: label strings terminated by blank
        if self.decoderType == DecoderType.WordBeamSearch:
            blank = len(self.charList)
            for b in range(batchSize):
                for label in ctcOutput[b]:
                    if label == blank:
                        break
                    encodedLabelStrs[b].append(label)

        # TF decoders: label strings are contained in sparse tensor
        else:
            # ctc returns tuple, first element is SparseTensor
            decoded = ctcOutput[0][0]

            # go over all indices and save mapping: batch -> values
            idxDict = {b: [] for b in range(batchSize)}
            for (idx, idx2d) in enumerate(decoded.indices):
                label = decoded.values[idx]
                batchElement = idx2d[0]  # index according to [b,t]
                encodedLabelStrs[batchElement].append(label)

        # map labels to chars for all batch elements
        return [str().join([self.charList[c] for c in labelStr]) for labelStr in
                encodedLabelStrs]

    def inferBatch(self, batch, calcProbability=False, probabilityOfGT=False):
        # decode, optionally save RNN output
        numBatchElements = len(batch.imgs)
        evalRnnOutput = self.dump or calcProbability
        evalList = [self.decoder] + ([self.ctcIn3dTBC] if evalRnnOutput else [])
        feedDict = {self.inputImgs: batch.imgs,
                    self.seqLen: [Model.maxTextLen] * numBatchElements,
                    self.is_train: False}
        evalRes = self.sess.run(evalList, feedDict)
        decoded = evalRes[0]
        texts = self.decoderOutputToText(decoded, numBatchElements)

        # feed RNN output and recognized text into CTC loss to compute labeling probability
        probs = None
        if calcProbability:
            sparse = self.toSparse(
                batch.gtTexts) if probabilityOfGT else self.toSparse(texts)
            ctcInput = evalRes[1]
            evalList = self.lossPerElement
            feedDict = {self.savedCtcInput: ctcInput, self.gtTexts: sparse,
                        self.seqLen: [Model.maxTextLen] * numBatchElements,
                        self.is_train: False}
            lossVals = self.sess.run(evalList, feedDict)
            probs = np.exp(-lossVals)

        return (texts, probs)
