import os
import sys
import math
import json
import argparse
import random
import ROOT
ROOT.PyConfig.IgnoreCommandLineOptions = True
from importlib import import_module

from PhysicsTools.NanoAODTools.postprocessing.framework.postprocessor import PostProcessor
from PhysicsTools.NanoAODTools.postprocessing.framework.datamodel import Collection, Object
from PhysicsTools.NanoAODTools.postprocessing.framework.eventloop import Module
from PhysicsTools.NanoAODTools.modules import *
from PhysicsTools.NanoAODTools.postprocessing.modules.jme.jetmetHelperRun2       import * 
from PhysicsTools.NanoAODTools.postprocessing.modules.jme.jetRecalib import *


parser = argparse.ArgumentParser()
parser.add_argument('--isData', dest='isData', action='store_true',default=False)
parser.add_argument('--year', dest='year', action='store',type=int, default=2016)
parser.add_argument('--input', dest='inputFiles', action='append',default=[])
parser.add_argument('output', nargs=1)

args = parser.parse_args()

print "isData:",args.isData
print "year:",args.year
print "inputs:",len(args.inputFiles)
for inputFile in args.inputFiles:
    rootFile = ROOT.TFile.Open(inputFile)
    if not rootFile:
        print "CRITICAL - file '"+inputFile+"' not found!"
        sys.exit(1)
    tree = rootFile.Get("Events")
    if not tree:
        print "CRITICAL - 'Events' tree not found in file '"+inputFile+"'!"
        sys.exit(1)
    print " - ",inputFile,", events=",tree.GetEntries()
    
print "output directory:",args.output[0]

globalOptions = {
    "isData":args.isData,
    "year":args.year
}

isMC = not args.isData

#jmeCorrections = createJMECorrector(isMC=isMC, dataYear=args.year, runPeriod="B", jesUncert="Total", redojec=True, jetType="AK4PFchs", noGroom=False, metBranchName="MET", applySmearing="True", isFastSim=False)
#jmeCorrections = createJMECorrector(isMC=isMC, dataYear="2018", runPeriod="B", jesUncert="Total", redojec=True, jetType="AK4PFchs", noGroom=False, metBranchName="MET", applySmearing="True", isFastSim=False)
jetRecalibration = jetRecalib(globalTag="Summer16_07Aug2017_V11_MC", archive="Summer16_07Aug2017_V11_MC", jetType="AK4PFchs", redoJEC=True)


muonSelection = [
    EventSkim(selection=lambda event: event.nTrigObj>0),
    MuonSelection(
        outputName="tightMuons",
        storeKinematics=['pt','eta', 'dxy', 'dxyErr', 'dz', 'dzErr', 'phi', 'pfRelIso04_all'],
        storeWeights=True,
        muonMinPt = 25.,
        triggerMatch = True,
        muonID = MuonSelection.TIGHT,
        muonIso = MuonSelection.TIGHT,
        globalOptions=globalOptions
    ),
    EventSkim(selection=lambda event: event.ntightMuons==1),
    MuonSelection(
        inputCollection = lambda event: [muon for muon in Collection(event, "Muon") if abs(muon.pt-event.tightMuons[0].pt)>1e-4],
        outputName="looseMuons",
        storeKinematics=['pt','eta', 'dxy', 'dxyErr', 'dz', 'dzErr', 'phi', 'pfRelIso04_all'],
        storeWeights=True,
        muonMinPt = 5.,
        muonID = MuonSelection.LOOSE,
        muonIso = MuonSelection.NONE,
        globalOptions=globalOptions
    ),
    
    SingleMuonTriggerSelection(
        inputCollection=lambda event: event["tightMuons"],
        outputName="IsoMuTrigger",
        storeWeights=False,
        globalOptions=globalOptions
    ),
    EventSkim(selection=lambda event: event.IsoMuTrigger_flag==1),
    EventSkim(selection=lambda event: event.nlooseMuons>0)
]

#analyzerChain = [jetRecalibration]
analyzerChain = []

analyzerChain.extend(muonSelection)

analyzerChain.append(
    JetSelection(
        leptonCollection=lambda event: event.tightMuons,

        globalOptions=globalOptions
    )
)


analyzerChain.append(EventSkim(selection=lambda event: len(event.selectedJets)>0))


analyzerChain.append(
    InvariantSystem(
        inputCollection = lambda event: [event.looseMuons[0], event.tightMuons[0]],
        outputName = "dimuon"
    )
)

analyzerChain.append(
    LepJetFinder(
        jetCollection = lambda event: event.selectedJets,
        leptonCollection = lambda event: event.looseMuons,
    )
)

analyzerChain.append(
    TaggerEvaluation(
        modelPath="PhysicsTools/NanoAODTools/data/nn/weight2016_75.pb",
        logctauValues = range(-1, 4),
        inputCollections=[
            lambda event: event.lepJet,
        ],
        taggerName="llpdnnx",
    )
)


analyzerChain.append(
    JetTaggerResult(
        inputCollection = lambda event: event.lepJet,
        taggerName = "llpdnnx",
        outputName = "lepJet",
        logctauValues = range(-1, 4),
    )
)

'''
analyzerChain.append(
    JetTruthFlags(inputCollection= lambda event: event.selectedJets,
        outputName="selectedJets"
    )
)
'''

analyzerChain.append(
    JetTruthFlags(inputCollection= lambda event: event.lepJet,
        globalOptions=globalOptions,
        outputName="lepJet"
    )
)

'''
analyzerChain.append(
    TaggerWorkingpoints(
        inputCollection = lambda event: event.selectedJets,
    )
)
'''

analyzerChain.append( 
     MetFilter()
)

analyzerChain.append(
     EventObservables(
       jetCollection = lambda event: event.selectedJets,
       leptonCollection = lambda event: event.tightMuons[0] 
     )
)

'''
 
analyzerChain.append(
    XGBEvaluation(
        modelPath="PhysicsTools/NanoAODTools/data/nn/bdt.model",
    )
)
'''

storeVariables = [
    [lambda tree: tree.branch("MET_pt", "F"), lambda tree,event: tree.fillBranch("MET_pt", event.MET_pt)],
    [lambda tree: tree.branch("MET_phi", "F"), lambda tree,event: tree.fillBranch("MET_phi", event.MET_phi)],
    [lambda tree: tree.branch("MET_significance", "F"), lambda tree,event: tree.fillBranch("MET_significance", event.MET_significance)],
    #[lambda tree: tree.branch("bdt_score", "F"), lambda tree,event: tree.fillBranch("bdt_score", event.bdt_score)]
]

if not globalOptions["isData"]:
    storeVariables.append([lambda tree: tree.branch("genweight","F"),lambda tree,event: tree.fillBranch("genweight",event.Generator_weight)])

T_ptT_ptT_ptT_ptT_ptT_ptT_ple
t
analyzerChain.append(EventInfo(storeVariables=storeVariables))

p=PostProcessor(
    args.output[0],
    [args.inputFiles],
    modules=analyzerChain,
    maxEvents=-1,
    friend=True
)
p.run()
