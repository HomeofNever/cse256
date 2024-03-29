# -*- coding: utf-8 -*-
"""Assignment4.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1by65pwmYI870HjDKak0CnX0KayWhFE8W
"""

import sys
from collections import defaultdict
import math
import json
import re

def basedir():
  return "/content/drive/MyDrive/Colab Notebooks/CSE256/A4_256_sp22"

"""
Evaluate gene tagger output by comparing it to a gold standard file.

Running the script on your tagger output like this

    python eval_gene_tagger.py gene_dev.key your_tagger_output.dat

will generate a table of results like this:

    Found 14071 GENES. Expected 5942 GENES; Correct: 3120.

		 precision 	recall 		F1-Score
    GENE:	 0.433367	0.231270	0.301593

Adopted from original named entity evaluation.

"""

def corpus_iterator(corpus_file, with_logprob = False):
    """
    Get an iterator object over the corpus file. The elements of the
    iterator contain (word, ne_tag) tuples. Blank lines, indicating
    sentence boundaries return (None, None).
    """
    l = corpus_file.readline()    
    tagfield = with_logprob and -2 or -1

    try:
        while l:
            line = l.strip()
            if line: # Nonempty line
                # Extract information from line.
                # Each line has the format
                # word ne_tag [log_prob]
                fields = line.split(" ")
                ne_tag = fields[tagfield]
                word = " ".join(fields[:tagfield])
                yield word, ne_tag
            else: # Empty line
                yield (None, None)
            l = corpus_file.readline()
    except IndexError:
        sys.stderr.write("Could not read line: \n")
        sys.stderr.write("\n%s" % line)
        if with_logprob:
            sys.stderr.write("Did you forget to output log probabilities in the prediction file?\n")
        raise IndexError

class NeTypeCounts(object):
    """
    Stores true/false positive/negative counts for each NE type.
    """

    def __init__(self):
        self.tp = 0
        self.fp = 0
        self.tn = 0
        self.fn = 0 

    def get_precision(self):
        return self.tp / float(self.tp + self.fp)

    def get_recall(self):
        return self.tp / float(self.tp + self.fn)

    def get_accuracy(self):
        return (self.tp + self.tn) / float(self.tp + self.tn + self.fp + self.fn)


class Evaluator(object):
    """
    Stores global true/false positive/negative counts. 
    """


    ne_classes = ["GENE"]

    def __init__(self):        
        self.tp = 0
        self.tn = 0
        self.fp = 0        
        self.fn = 0

        # Initialize an object that counts true/false positives/negatives
        # for each NE class
        self.class_counts = {}
        for c in self.ne_classes:
            self.class_counts[c] = NeTypeCounts()

    def compare(self, gold_standard, prediction):
        """
        Compare the prediction against a gold standard. Both objects must be
        generator or iterator objects that return a (word, ne_tag) tuple at a
        time.
        """

        # Define a couple of tags indicating the status of each stream
        curr_pred_type = None # prediction stream was previously in a named entity
        curr_pred_start = None # a new prediction starts at the current token
        curr_gs_type = None   # prediction stream was previously in a named entity
        curr_gs_start = None # a new prediction starts at the current token

        total = 0
        for gs_word, gs_tag in gold_standard: # Move through the gold standard stream
            pred_word, pred_tag = next(prediction) # Get the corresponding item from the prediction stream
            
            # Make sure words in both files match up
            if gs_word != pred_word:
                sys.stderr.write("Could not align gold standard and predictions in line %i.\n" % (total+1))
                sys.stderr.write("Gold standard: %s  Prediction file: %s\n" % (gs_word, pred_word))
                raise KeyError        

            # Split off the I and B tags
            gs_type = gs_tag==None and "O" or gs_tag.split("-")[-1]
            pred_type = pred_tag==None and "O" or pred_tag.split("-")[-1]                        

            # Check if a named entity ends here in either stream.
            # This is the case if we are currently in an entity and either
            #   - end of sentence
            #   - current word is marked O
            #   - new entity starts (B - or I with different NE type)
            pred_ends = curr_pred_type!=None and ((pred_tag==None or pred_tag[0] in "OB") or (curr_pred_type!=pred_type and pred_tag[0]=="I"))
            gs_ends = curr_gs_type!=None and ((gs_tag==None or gs_tag[0] in "OB") or (curr_gs_type!=gs_type and gs_tag[0]=="I"))
            

            # Check if a named entity starts here in either stream.
            # This is tha case if this is not the end of a sentence and
            #   - This is not the end of a sentence
            #   - New entity starts (B, I after O or at begining of sentence or
            #       I with different NE type) 
            if pred_word!=None:
                pred_start = (pred_tag!=None and pred_tag[0] == "B") or (curr_pred_type==None and pred_tag[0]=="I") or \
                    (curr_pred_type!=None and curr_pred_type!=pred_type and pred_tag.startswith("I"))
                gs_starts = (gs_tag!=None and gs_tag[0] == "B") or (curr_gs_type==None and gs_tag[0]=="I") or \
                    (curr_gs_type!=None and curr_gs_type!=gs_type and gs_tag.startswith("I"))
            else:
                pred_start = False
                gs_starts = False            

            #For debugging:
            #print pred_word, gs_tag, pred_tag, pred_ends, gs_ends, pred_start, gs_starts


            # Now try to match up named entities that end here

            if gs_ends and pred_ends: # GS and prediction contain a named entity that ends in the same place

                #If both named entities start at the same place and are of the same type
                if curr_gs_start == curr_pred_start and curr_gs_type == curr_pred_type:
                    # Count true positives
                    self.tp += 1
                    self.class_counts[curr_pred_type].tp += 1
                else: #span matches, but label doesn't match: count both a true positive and a false negative
                    self.fp += 1
                    self.fn += 1
                    self.class_counts[curr_pred_type].fp += 1
                    self.class_counts[curr_gs_type].fn += 1
            elif gs_ends: #Didn't find the named entity in the gold standard, count false negative
                self.fn += 1
                self.class_counts[curr_gs_type].fn += 1
            elif pred_ends: #Named entity in the prediction doesn't match one int he gold_standard, count false positive
                self.fp += 1
                self.class_counts[curr_pred_type].fp += 1
            elif curr_pred_type==None and curr_pred_type==None: #matching O tag or end of sentence, count true negative
                self.tn += 1
                for c in self.ne_classes:
                    self.class_counts[c].tn += 1

            # Remember that we are no longer in a named entity
            if gs_ends:
                curr_gs_type = None
            if pred_ends:
                curr_pred_type = None

            # If a named entity starts here, remember it's type and this position
            if gs_starts:
                curr_gs_start = total
                curr_gs_type = gs_type
            if pred_start:
                curr_pred_start = total
                curr_pred_type = pred_type
            total += 1

    def print_scores(self):
        """
        Output a table with accuracy, precision, recall and F1 score. 
        """

        print ("Found %i GENEs. Expected %i GENEs; Correct: %i.\n" % (self.tp + self.fp, self.tp + self.fn, self.tp))


        if self.tp + self.tn + self.fp + self.fn == 0: # There was nothing to do.
            acc = 1
        else:
            acc = (self.tp + self.tn) / float(self.tp + self.tn + self.fp + self.fn)

        if self.tp+self.fp == 0:   # Prediction didn't annotate any NEs
            prec = 1
            
        else:
            prec = self.tp / float(self.tp + self.fp)
            

        if self.tp+self.fn == 0: # Prediction marked everything as a NE of the wrong type.
            rec = 1
        else:
            rec = self.tp / float(self.tp + self.fn)

        print ("\t precision \trecall \t\tF1-Score")
        fscore = (2*prec*rec)/(prec+rec)
        #print "Total:\t %f\t%f\t%f" % (prec, rec, fscore)
        for c in self.ne_classes:
            c_tp = self.class_counts[c].tp
            c_tn = self.class_counts[c].tn
            c_fp = self.class_counts[c].fp
            c_fn = self.class_counts[c].fn
            #print c
            #print c_tp
            #print c_tn
            #print c_fp
            #print c_fn
            if (c_tp + c_tn + c_fp + c_fn) == 0:                
                c_acc = 1
            else:
                c_acc = (c_tp + c_tn) / float(c_tp + c_tn + c_fp + c_fn)
            
            if (c_tp + c_fn) == 0:
                sys.stderr.write("Warning: no instances for entity type %s in gold standard.\n" % c)
                c_rec = 1
            else:
                c_rec = c_tp / float(c_tp + c_fn)
            if (c_tp + c_fp) == 0:
                sys.stderr.write("Warning: prediction file does not contain any instances of entity type %s.\n" % c)
                c_prec =1
            else:
                c_prec = c_tp / float(c_tp + c_fp)

            if c_prec + c_rec == 0:
                fscore = 0
            else:    
                fscore = (2*c_prec * c_rec)/(c_prec + c_rec)
            print ("%s:\t %f\t%f\t%f" % (c, c_prec, c_rec, fscore))

def eval_gene_tagger(your_file, prediction_file):
    """
    Usage: python eval_gene_tagger.py [key_file] [prediction_file]
        Evaluate the gene-tagger output in prediction_file against
        the gold standard in key_file. Output accuracy, precision,
        recall and F1-Score.\n
    """
    bd = basedir()
    gs_iterator = corpus_iterator(open(bd + "/" + your_file))
    pred_iterator = corpus_iterator(open(bd + "/" + prediction_file), with_logprob = False)
    evaluator = Evaluator()
    evaluator.compare(gs_iterator, pred_iterator)
    evaluator.print_scores()
    return evaluator

"""
Count n-gram frequencies in a data file and write counts to
stdout. 
"""

def simple_conll_corpus_iterator(corpus_file):
    """
    Get an iterator object over the corpus file. The elements of the
    iterator contain (word, ne_tag) tuples. Blank lines, indicating
    sentence boundaries return (None, None).
    """
    l = corpus_file.readline()
    while l:
        line = l.strip()
        if line: # Nonempty line
            # Extract information from line.
            # Each line has the format
            # word pos_tag phrase_tag ne_tag
            fields = line.split(" ")
            ne_tag = fields[-1]
            #phrase_tag = fields[-2] #Unused
            #pos_tag = fields[-3] #Unused
            word = " ".join(fields[:-1])
            yield word, ne_tag
        else: # Empty line
            yield (None, None)                        
        l = corpus_file.readline()

def sentence_iterator(corpus_iterator):
    """
    Return an iterator object that yields one sentence at a time.
    Sentences are represented as lists of (word, ne_tag) tuples.
    """
    current_sentence = [] #Buffer for the current sentence
    for l in corpus_iterator:        
            if l==(None, None):
                if current_sentence:  #Reached the end of a sentence
                    yield current_sentence
                    current_sentence = [] #Reset buffer
                else: # Got empty input stream
                    sys.stderr.write("WARNING: Got empty input file/stream.\n")
                    raise StopIteration
            else:
                current_sentence.append(l) #Add token to the buffer

    if current_sentence: # If the last line was blank, we're done
        yield current_sentence  #Otherwise when there is no more token
                                # in the stream return the last sentence.

def get_ngrams(sent_iterator, n):
    """
    Get a generator that returns n-grams over the entire corpus,
    respecting sentence boundaries and inserting boundary tokens.
    Sent_iterator is a generator object whose elements are lists
    of tokens.
    """
    for sent in sent_iterator:
         #Add boundary symbols to the sentence
         w_boundary = (n-1) * [(None, "*")]
         w_boundary.extend(sent)
         w_boundary.append((None, "STOP"))
         #Then extract n-grams
         ngrams = (tuple(w_boundary[i:i+n]) for i in range(len(w_boundary)-n+1))
         for n_gram in ngrams: #Return one n-gram at a time
            yield n_gram        


class Hmm(object):
    """
    Stores counts for n-grams and emissions. 
    """

    def __init__(self, n=3):
        assert n>=2, "Expecting n>=2."
        self.n = n
        self.emission_counts = defaultdict(int)
        self.ngram_counts = [defaultdict(int) for i in range(self.n)]
        self.all_states = set()

    def train(self, corpus_file):
        """
        Count n-gram frequencies and emission probabilities from a corpus file.
        """
        ngram_iterator = \
            get_ngrams(sentence_iterator(simple_conll_corpus_iterator(corpus_file)), self.n)

        for ngram in ngram_iterator:
            #Sanity check: n-gram we get from the corpus stream needs to have the right length
            assert len(ngram) == self.n, "ngram in stream is %i, expected %i" % (len(ngram, self.n))

            tagsonly = tuple([ne_tag for word, ne_tag in ngram]) #retrieve only the tags            
            for i in range(2, self.n+1): #Count NE-tag 2-grams..n-grams
                self.ngram_counts[i-1][tagsonly[-i:]] += 1
            
            if ngram[-1][0] is not None: # If this is not the last word in a sentence
                self.ngram_counts[0][tagsonly[-1:]] += 1 # count 1-gram
                self.emission_counts[ngram[-1]] += 1 # and emission frequencies

            # Need to count a single n-1-gram of sentence start symbols per sentence
            if ngram[-2][0] is None: # this is the first n-gram in a sentence
                self.ngram_counts[self.n - 2][tuple((self.n - 1) * ["*"])] += 1

    def train_iter(self, f_iterator):
        """
        Count n-gram frequencies and emission probabilities from a corpus file.
        """
        ngram_iterator = \
            get_ngrams(sentence_iterator(f_iterator), self.n)

        for ngram in ngram_iterator:
            #Sanity check: n-gram we get from the corpus stream needs to have the right length
            assert len(ngram) == self.n, "ngram in stream is %i, expected %i" % (len(ngram, self.n))

            tagsonly = tuple([ne_tag for word, ne_tag in ngram]) #retrieve only the tags            
            for i in range(2, self.n+1): #Count NE-tag 2-grams..n-grams
                self.ngram_counts[i-1][tagsonly[-i:]] += 1
            
            if ngram[-1][0] is not None: # If this is not the last word in a sentence
                self.ngram_counts[0][tagsonly[-1:]] += 1 # count 1-gram
                self.emission_counts[ngram[-1]] += 1 # and emission frequencies

            # Need to count a single n-1-gram of sentence start symbols per sentence
            if ngram[-2][0] is None: # this is the first n-gram in a sentence
                self.ngram_counts[self.n - 2][tuple((self.n - 1) * ["*"])] += 1

    def write_counts(self, output, printngrams=[1,2,3]):
        """
        Writes counts to the output file object.
        Format:

        """
        # First write counts for emissions
        for word, ne_tag in self.emission_counts:            
            output.write("%i WORDTAG %s %s\n" % (self.emission_counts[(word, ne_tag)], ne_tag, word))


        # Then write counts for all ngrams
        for n in printngrams:            
            for ngram in self.ngram_counts[n-1]:
                ngramstr = " ".join(ngram)
                output.write("%i %i-GRAM %s\n" %(self.ngram_counts[n-1][ngram], n, ngramstr))
    
    def get_write_counts(self):
        """
        Get Count Directly without writing to file
        """
        printngrams=[i for i in range(1, self.n + 1)]
        # First write counts for emissions
        wordtag = dict()
        for word, ne_tag in self.emission_counts:   
            wordtag[(word, ne_tag)] = self.emission_counts[(word, ne_tag)]

        # Then write counts for all ngrams
        ngram_tag = dict()
        for i in printngrams:
          ngram_tag[i] = dict()

        for n in printngrams:       
            for ngram in self.ngram_counts[n-1]:
                ngram_tag[n][ngram] = self.ngram_counts[n-1][ngram]

        return {
            "wordtag": wordtag,
            "ngram_tag": ngram_tag
        }

    def read_counts(self, corpusfile):

        self.n = 3
        self.emission_counts = defaultdict(int)
        self.ngram_counts = [defaultdict(int) for i in xrange(self.n)]
        self.all_states = set()

        for line in corpusfile:
            parts = line.strip().split(" ")
            count = float(parts[0])
            if parts[1] == "WORDTAG":
                ne_tag = parts[2]
                word = parts[3]
                self.emission_counts[(word, ne_tag)] = count
                self.all_states.add(ne_tag)
            elif parts[1].endswith("GRAM"):
                n = int(parts[1].replace("-GRAM",""))
                ngram = tuple(parts[2:])
                self.ngram_counts[n-1][ngram] = count
                

def count_freqs(input_file, output_file):
    """
    python count_freqs.py [input_file] > [output_file]
        Read in a gene tagged training input file and produce counts.
    """
    ins = basedir() + "/" + input_file
    try:
        input = open(ins,"r")
    except IOError:
        sys.stderr.write("ERROR: Cannot read inputfile %s.\n" % ins)
        return
    
    # Initialize a trigram counter
    counter = Hmm(3)
    # Collect counts
    counter.train(input)
    # Write the counts
    counter.write_counts(open(basedir() + "/" + output_file, "w"))


def get_count_freqs(input_file, ngram=3):
    ins = basedir() + "/" + input_file
    try:
        input = open(ins,"r")
    except IOError:
        sys.stderr.write("ERROR: Cannot read inputfile %s.\n" % ins)
        return
    
    # Initialize a trigram counter
    counter = Hmm(ngram)
    # Collect counts
    counter.train(input)
    return counter.get_write_counts()

tags = get_count_freqs("gene.train")

def calculate_emission_params(tags, shouldLog = False):
    wordtag = tags['wordtag']
    ngram = tags['ngram_tag'][1]

    res = defaultdict(int)
    for tag, value in wordtag.items():
      if shouldLog:
        res[tag] = math.log(value / ngram[(tag[1],)], 2)
      else:
        res[tag] = value / ngram[(tag[1],)]

    return res

t_emi = calculate_emission_params(tags)
print(list(t_emi.items())[0])

RARE_SYM = "_RARE_"

def replace_rare_word(file, freq=5, sym=RARE_SYM):
  freq_map = defaultdict(int)

  with open(file) as f:
    for i in simple_conll_corpus_iterator(f):
      freq_map[i[0]] += 1
  
  words = []
  with open(file) as f:
    for i in simple_conll_corpus_iterator(f):
      if freq_map[i[0]] < freq:
        words.append((RARE_SYM, i[1]))
      else:
        words.append(i)

  return words, freq_map

def dict_get_count_freq(iter, ngram=3):
  # Initialize a trigram counter
  counter = Hmm(ngram)
  # Collect counts
  counter.train_iter(iter)
  return counter.get_write_counts()

IS_GENE = "I-GENE"
NOT_GENE = "O"

def simple_tagger(count_dict, input_file):
  """
  return list [word->tag]
  """
  t_emi = calculate_emission_params(count_dict)

  allWords = set()
  for i in t_emi.keys():
    allWords.add(i[0])

  res = []
  # Pre calculate rare
  rare_is_gene = t_emi[(RARE_SYM, IS_GENE)]
  rare_not_gene = t_emi[(RARE_SYM, NOT_GENE)]
  rare_tag = IS_GENE
  if rare_is_gene < rare_not_gene:
    rare_tag = NOT_GENE

  with open(input_file) as f:
    for word in f:
      word = word.strip()
      if word == "":
        res.append(("", ""))
        continue
      
      if word in allWords:
        isGene = t_emi[(word, IS_GENE)]
        notGene = t_emi[(word, NOT_GENE)]

        if isGene > notGene:
          res.append((word, IS_GENE))
        else:
          res.append((word, NOT_GENE))
      else:
        res.append((word, rare_tag))
  
  return res


def tag2file(tags, file):
  with open(file, "w") as f:
    for word_pair in tags:
      f.write("{} {}\n".format(*word_pair))

outfile = "/gene_dev.p1.out"
replaced_train_data, freq_map = replace_rare_word(basedir() + "/gene.train")
rare_tags_count = dict_get_count_freq(iter(replaced_train_data))
tags = simple_tagger(rare_tags_count, basedir() + "/gene.dev")
tag2file(tags, basedir() + outfile)

#### Part 2 Baseline
eval_p1 = eval_gene_tagger("gene.key", "gene_dev.p1.out")

### Q2 Extension
'''
So, we could have:
  initCap
  Symbol(only)
  Digit(only)
  in these rare word group
'''

SYM_INIT_CAP = "_SYM_INIT_CAP"
SYM_SYMBOL = "_SYM_SYMBOL"
SYM_DIGIT = "_SYM_DIGIT"
SYM_LOWERCASE = "_SYM_LOWERCASE"
available_symbols=[SYM_INIT_CAP, SYM_SYMBOL, SYM_DIGIT, SYM_LOWERCASE]
  
def custom_convert(word, symbols=available_symbols):
  if SYM_INIT_CAP in symbols and word.istitle():
    return SYM_INIT_CAP
  if SYM_SYMBOL in symbols and re.match(r'^[_\W]+$', word):
    return SYM_SYMBOL
  if SYM_DIGIT in symbols and word.isdigit():
    return SYM_DIGIT
  if SYM_LOWERCASE in symbols and word.islower():
    return SYM_LOWERCASE
  
  return RARE_SYM

def replace_rare_word_extended(file, freq=5, symbols=available_symbols):
  freq_map = defaultdict(int)

  with open(file) as f:
    for i in simple_conll_corpus_iterator(f):
      freq_map[i[0]] += 1
  
  words = []
  with open(file) as f:
    for i in simple_conll_corpus_iterator(f):
      word = i[0]
      if freq_map[word] < freq:
        words.append((custom_convert(word, symbols), i[1]))
      else:
        words.append(i)

  return words, freq_map

def simple_tagger_extended(count_dict, input_file, symbols=available_symbols):
  """
  return list [word->tag]
  """
  t_emi = calculate_emission_params(count_dict)

  allWords = set()
  for i in t_emi.keys():
    allWords.add(i[0])

  res = []
  # Pre calculate rare
  symbols = symbols + [RARE_SYM]
  def getSymDict():
    symdict = dict()
    for s in symbols:
      is_gene = t_emi[(s, IS_GENE)]
      not_gene = t_emi[(s, NOT_GENE)]
      ttag = IS_GENE
      if is_gene < not_gene:
        ttag = NOT_GENE
      symdict[s] = ttag
    return symdict
  symdict = getSymDict()

  with open(input_file) as f:
    for word in f:
      word = word.strip()
      if word == "":
        res.append(("", ""))
        continue
      
      if word in allWords:
        isGene = t_emi[(word, IS_GENE)]
        notGene = t_emi[(word, NOT_GENE)]

        if isGene > notGene:
          res.append((word, IS_GENE))
        else:
          res.append((word, NOT_GENE))
      else:
        res.append((word, symdict[custom_convert(word, symbols)]))
  
  return res

p21outfile = "/gene_dev.p2.1.out"
symbols = [SYM_SYMBOL]

replaced_train_data_extended, freq_map_extended = replace_rare_word_extended(basedir() + "/gene.train", symbols=symbols)
rare_tags_count_extended = dict_get_count_freq(iter(replaced_train_data_extended))
tags_extended = simple_tagger_extended(rare_tags_count_extended, basedir() + "/gene.dev", symbols=symbols)
tag2file(tags_extended, basedir() + p21outfile)

p22outfile = "/gene_dev.p2.2.out"
symbols = available_symbols

replaced_train_data_extended, freq_map_extended = replace_rare_word_extended(basedir() + "/gene.train", symbols=symbols)
rare_tags_count_extended = dict_get_count_freq(iter(replaced_train_data_extended))
tags_extended = simple_tagger_extended(rare_tags_count_extended, basedir() + "/gene.dev", symbols=symbols)
tag2file(tags_extended, basedir() + p22outfile)

print("baseline: ")
eval_gene_tagger("gene.key", outfile)
print("----------------------------")
print("group: symbol only")
eval_gene_tagger("gene.key", p21outfile)
print("----------------------------")
print("group: all features")
eval_gene_tagger("gene.key", p22outfile)

##### Part 3
##### Reuse Emission value calculator

tags = get_count_freqs("gene.train")
t_emi = calculate_emission_params(tags)

def trigramParams(tags, shouldLog = False): 
  """
  Pre-calculate trigram params
  """
  threeTags = tags['ngram_tag'][3]
  twoTags = tags['ngram_tag'][2]
  trigramP = defaultdict(float)
  for key, value in threeTags.items():
    if shouldLog:
      trigramP[key] = math.log(value / twoTags[key[:2]], 2)
    else:
      trigramP[key] = value / twoTags[key[:2]]
  
  return trigramP

tri_emi = trigramParams(tags)

def print_dict(di):
    nd = dict()
    for key, value in di.items():
        nd[', '.join(map(str, key))] = value
    print(json.dumps(nd, sort_keys=True, indent=4))

print_dict(tri_emi)

### Verbiti
STOP_WORD = "STOP"

def verbiti(sentence, tri_emi, t_emi, vocab, symbols=[]):
  """
  sentence: [list of word]
  Return a list of word with corresponed [(word, tag)]
  """
  tags = [IS_GENE, NOT_GENE]
  len_of_sentence = len(sentence)
  # Create the matrix based on the length of sentence and tag
  # STOP aggragrate counts separately
  pi = defaultdict(float)
  pi[(0,"*", "*")] = 1
  bp = dict()

  def get_t_emi_prob(word, tag):
    if word in vocab:
      return t_emi[(word, tag)]
    else:
      if len(symbols) == 0:
        return t_emi[(RARE_SYM, tag)]
      else:
        return t_emi[(custom_convert(word, symbols), tag)]

  # Calculate the first col of the matrix
  if len_of_sentence > 0:
    k, w, u = 1, "*", "*"
    for v in tags:
      next_pi = pi[(k - 1, w, u)] * tri_emi[(w, u, v)] * get_t_emi_prob(sentence[0], v)
      pi[(k, u, v)] = max(pi[(k, u, v)], next_pi)
      bp[(k, u, v)] = "*"

  # Calculate the second col
  if len_of_sentence > 1:
    k, w = 2, "*"
    for v in tags:
      for u in tags:
        next_pi = pi[(k - 1, w, u)] * tri_emi[(w, u, v)] * get_t_emi_prob(sentence[1], v)
        pi[(k, u, v)] = max(pi[(k, u, v)], next_pi)
        bp[(k, u, v)] = "*"

  if len_of_sentence > 2:
    # Loop for the rest
    for k in range(2, len_of_sentence):
      for v in tags:
        for u in tags:
          next_bp = None
          for w in tags:
              next_pi = pi[(k, w, u)] * tri_emi[(w, u, v)] * get_t_emi_prob(sentence[k], v)
              if next_pi > pi[(k + 1, u, v)]:
                pi[(k + 1, u, v)] = next_pi
                next_bp = w
          bp[(k + 1, u, v)] = next_bp

  # Find max start by stop case
  first_last, second_last = None, None
  max_p = 0
  for u in tags:
      for v in tags:
          p = pi[(len_of_sentence, u, v)] * tri_emi[(u, v, STOP_WORD)]
          if p > max_p:
              second_last, first_last = u, v
              max_p = p

  res = [None] * len_of_sentence
  res[-1] = (sentence[-1], first_last)
  res[-2] = (sentence[-2], second_last)

  # Loop from the back and retrieve list
  # Remember to skip first 2, STOP calculate last two tag
  for k in range(len_of_sentence - 3, -1, -1):
    res[k] = (sentence[k], bp[(k+3, res[k+1][1], res[k+2][1])])

  return res

def verbiti_tagger(count_dict, input_file, symbols=[]):
  """
  return list [word->tag]
  """
  t_emi = calculate_emission_params(count_dict)
  tri_emi = trigramParams(count_dict)
  allWords = set()
  for i in t_emi.keys():
    allWords.add(i[0])


  # For input file, we have to first read the whole sentence
  res = []
  with open(input_file) as f:
    sentence = []
    for word in f:
      word = word.strip()
      if word == "":
        final_res = verbiti(sentence, tri_emi, t_emi, allWords, symbols)
        res += final_res
        res.append(("", ""))
        sentence = []
      else:
        sentence.append(word)
  
  return res

verb_outfile = "/gene_dev.verb.out"
replaced_train_data, freq_map = replace_rare_word(basedir() + "/gene.train")
rare_tags_count = dict_get_count_freq(iter(replaced_train_data))
tags = verbiti_tagger(rare_tags_count, basedir() + "/gene.dev")
tag2file(tags, basedir() + outfile)

eval_verb = eval_gene_tagger("gene.key", outfile)

#### Part 3 Extension
p31outfile = "/gene_dev.p3.1.out"
symbols = [SYM_SYMBOL]

replaced_train_data_extended, freq_map_extended = replace_rare_word_extended(basedir() + "/gene.train", symbols=symbols)
rare_tags_count_extended = dict_get_count_freq(iter(replaced_train_data_extended))
tags_extended = verbiti_tagger(rare_tags_count_extended, basedir() + "/gene.dev", symbols)
tag2file(tags_extended, basedir() + p31outfile)

p32outfile = "/gene_dev.p3.2.out"
symbols = available_symbols

replaced_train_data_extended, freq_map_extended = replace_rare_word_extended(basedir() + "/gene.train", symbols=symbols)
rare_tags_count_extended = dict_get_count_freq(iter(replaced_train_data_extended))
tags_extended = verbiti_tagger(rare_tags_count_extended, basedir() + "/gene.dev", symbols)
tag2file(tags_extended, basedir() + p32outfile)

print("baseline: ")
eval_gene_tagger("gene.key", verb_outfile)
print("----------------------------")
print("group: symbol only")
eval_gene_tagger("gene.key", p31outfile)
print("----------------------------")
print("group: all feature")
eval_gene_tagger("gene.key", p32outfile)

##### four-gram

tags = get_count_freqs("gene.train", ngram=4)
t_emi = calculate_emission_params(tags)

def fourgramParams(tags): 
  """
  Pre-calculate trigram params
  """
  threeTags = tags['ngram_tag'][4]
  twoTags = tags['ngram_tag'][3]
  trigramP = defaultdict(float)
  for key, value in threeTags.items():
      trigramP[key] = value / twoTags[key[:3]]
  
  return trigramP

for_emi = fourgramParams(tags)
print_dict(for_emi)

def verbiti4(sentence, tri_emi, t_emi, vocab, symbols=[]):
  """
  sentence: [list of word]
  Return a list of word with corresponed [(word, tag)]
  """
  tags = [IS_GENE, NOT_GENE]
  len_of_sentence = len(sentence)
  # Create the matrix based on the length of sentence and tag
  # STOP aggragrate counts separately
  pi = defaultdict(float)
  pi[(0,"*", "*", "*")] = 1
  bp = dict()

  def get_t_emi_prob(word, tag):
    if word in vocab:
      return t_emi[(word, tag)]
    else:
      if len(symbols) == 0:
        return t_emi[(RARE_SYM, tag)]
      else:
        return t_emi[(custom_convert(word, symbols), tag)]

  # Calculate the first col of the matrix
  if len_of_sentence > 0:
    k, x, w, u = 1, "*", "*", "*"
    for v in tags:
      next_pi = pi[(k - 1, x, w, u)] * tri_emi[(x, w, u, v)] * get_t_emi_prob(sentence[0], v)
      pi[(k, w, u, v)] = max(pi[(k, w, u, v)], next_pi)
      bp[(k, w, u, v)] = "*"

  # Calculate the second col
  if len_of_sentence > 1:
    k, x, w = 2, "*", "*"
    for v in tags:
      for u in tags:
        next_pi = pi[(k - 1, x, w, u)] * tri_emi[(x, w, u, v)] * get_t_emi_prob(sentence[1], v)
        pi[(k, w, u, v)] = max(pi[(k, w, u, v)], next_pi)
        bp[(k, w, u, v)] = "*"

  if len_of_sentence > 2:
    k, x = 3, "*",
    for v in tags:
      for u in tags:
        for w in tags: 
          next_pi = pi[(k - 1, x, w, u)] * tri_emi[(x, w, u, v)] * get_t_emi_prob(sentence[2], v)
          pi[(k, w, u, v)] = max(pi[(k, w, u, v)], next_pi)
          bp[(k, w, u, v)] = "*"
    
  if len_of_sentence > 3:
    # Loop for the rest
    for k in range(3, len_of_sentence):
      for v in tags:
        for u in tags:
          for w in tags:
            next_bp = None
            for x in tags:
              next_pi = pi[(k, x, w, u)] * tri_emi[(x, w, u, v)] * get_t_emi_prob(sentence[k], v)
              if next_pi > pi[(k + 1, w, u, v)]:
                pi[(k + 1, w, u, v)] = next_pi
                next_bp = x
            bp[(k + 1, w, u, v)] = next_bp

  # Find max start by stop case
  first_last, second_last, third_last = None, None, None
  max_p = 0
  for w in tags:
    for u in tags:
        for v in tags:
            p = pi[(len_of_sentence, w, u, v)] * tri_emi[(w, u, v, STOP_WORD)]
            if p > max_p:
                third_last, second_last, first_last = w, u, v
                max_p = p

  res = [None] * len_of_sentence

  if len_of_sentence > 0:
    res[-1] = (sentence[-1], first_last)
  if len_of_sentence > 1:
    res[-2] = (sentence[-2], second_last)
  if len_of_sentence > 2:
    res[-3] = (sentence[-3], third_last)
  # Loop from the back and retrieve list
  # Remember to skip first 2, STOP calculate last three tag
  if len_of_sentence > 3:
    for k in range(len_of_sentence - 4, -1, -1):
      res[k] = (sentence[k], bp[(k+4, res[k+1][1], res[k+2][1], res[k+3][1])])

  return res

def verbiti4_tagger(count_dict, input_file, symbols=[]):
  """
  return list [word->tag]
  """
  t_emi = calculate_emission_params(count_dict)
  tri_emi = fourgramParams(count_dict)
  allWords = set()
  for i in t_emi.keys():
    allWords.add(i[0])


  # For input file, we have to first read the whole sentence
  res = []
  with open(input_file) as f:
    sentence = []
    for word in f:
      word = word.strip()
      if word == "":
        final_res = verbiti4(sentence, tri_emi, t_emi, allWords, symbols)
        res += final_res
        res.append(("", ""))
        sentence = []
      else:
        sentence.append(word)
  
  return res

verb4_outfile = "/gene_dev.verb4.out"
replaced_train_data, freq_map = replace_rare_word(basedir() + "/gene.train")
rare_tags_count = dict_get_count_freq(iter(replaced_train_data), ngram=4)
tags = verbiti4_tagger(rare_tags_count, basedir() + "/gene.dev")
tag2file(tags, basedir() + verb4_outfile)

print("vibi tri: ")
eval_gene_tagger("gene.key", verb_outfile)
print("----------------------------")
print("vibi four:")
eval_gene_tagger("gene.key", verb4_outfile)