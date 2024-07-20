from transformers import AutoTokenizer, AutoModelForSequenceClassification
from transformers import pipeline

import torch
import pandas as pd

import spacy

def score_sentence(text: str)-> pd.DataFrame:
    '''
    Takes the full body text of the MD&A from a single edgar filing, and returns a DataFrame containing the original text, predicted label, and sentiment score
    '''
    #segment sentences and store as list of strings
    doc = list(sent_seg(text).sents)
    doc = [elem.text for elem in doc]

    #label sentences
    scores_and_labels = pipe(doc)

    #convert both sentence list and score/labels list into DataFrames
    doc = pd.DataFrame(doc, columns= ['sentence'])
    scores_and_labels = pd.DataFrame(scores_and_labels)

    #enter predicted label and score into the sentence DataFrame
    doc['label'], doc['score'] = scores_and_labels['label'], scores_and_labels['score']

    return doc

sent_seg = spacy.load("en_core_web_sm")

tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

pipe = pipeline(task='text-classification', model= model, tokenizer= tokenizer, device= device)