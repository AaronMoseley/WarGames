from torch import nn
from torch.nn import functional as F
import torch
import torchvision.models
from typing import Type, Union, Optional, Callable, List 
import numpy as np
import MinMaxAI
import copy
from RLModel import ResNetEncoder, BasicBlock
import LevelManager
import random
import time
import math

class MinMaxWarGamesAI(nn.Module):
    def __init__(self, device) -> None:
        super().__init__()

        self.device = device
        self.resnet = ResNetEncoder(inlayers=2, block=BasicBlock, layers=[2, 2, 2, 2], num_classes=1).to(device)

    def forward(self, levelStates, buildingTurnCounters, currPlayer, returnMove=True, stateBudget=2500):
        result = []
        
        for i, levelState in enumerate(levelStates):
            buildingTurnCounter = buildingTurnCounters[i]
            validMoves = MinMaxAI.getValidMoves(levelState, currPlayer)
        
            if len(validMoves) == 0:
                result.append(None if returnMove else 0)
                continue
            
            random.seed(time.time())

            random.shuffle(validMoves)

            for i in range(len(validMoves)):
                if MinMaxAI.isCreateOrCapture(levelState, validMoves[i]):
                    validMoves.insert(0, validMoves.pop(i))

            currDepth = 2

            finalMove = None
            modelInput = None

            while stateBudget > 0:
                bestUtil = -float("inf")
                bestMove = None
                alpha = -float("inf")
                beta = float("inf")

                for move in validMoves:
                    newState = copy.deepcopy(levelState)
                    newTurnCounter = copy.deepcopy(buildingTurnCounter)

                    newState, newTurnCounter = LevelManager.makeMove(newState, newTurnCounter, move)
                    newState, newTurnCounter = LevelManager.incrementTurn(newState, newTurnCounter)

                    if returnMove:
                        util, stateBudget = self.minimax(newState, newTurnCounter, 2, currDepth, True, alpha, beta, currPlayer * -1, currPlayer, stateBudget)

                        if util == None or stateBudget <= -1:
                            break

                        if util > bestUtil:
                            bestUtil = util
                            bestMove = move
                            alpha = max(alpha, bestUtil)

                        currDepth += 1
                        finalMove = bestMove
                    else:
                        if modelInput == None:
                            modelInput = torch.from_numpy(np.array(newState)).unsqueeze(dim=0)
                            modelInput = torch.cat((modelInput, torch.from_numpy(np.array(newTurnCounter)).unsqueeze(dim=0))).to(self.device).unsqueeze(dim=0)
                        else:
                            newInput = torch.from_numpy(np.array(newState)).unsqueeze(dim=0)
                            newInput = torch.cat((newInput, torch.from_numpy(np.array(newTurnCounter)).unsqueeze(dim=0))).to(self.device).unsqueeze(dim=0)
                            modelInput = torch.cat((modelInput, newInput))

                if not returnMove:
                    bestUtil = torch.max(self.resnet(modelInput.float(), useSigm=False, getConv=False))
                    break

            if finalMove == None and bestUtil == -float("inf"):
                result.append(random.choice(validMoves) if returnMove else 0)
                #result.append(validMoves[0] if returnMove else 0)
            else:
                result.append(finalMove if returnMove else bestUtil)
            
        return result

        #result = np.array(result)
        #return torch.from_numpy(result)
    
    def minimax(self, currState, currTurnCounter, currDepth, maxDepth, isMaximizing, alpha, beta, currPlayer, startingPlayer, stateBudget):
        if stateBudget <= 0:
            return None, -1
        
        if LevelManager.checkWinCond(currState) != 0:
            return (float("inf"), stateBudget - 1) if startingPlayer == math.copysign(startingPlayer, LevelManager.checkWinCond(currState)) else (float("-inf"), stateBudget - 1)
        
        if currDepth >= maxDepth:
            modelInput = torch.from_numpy(np.array(currState)).unsqueeze(dim=0)
            modelInput = torch.cat((modelInput, torch.from_numpy(np.array(currTurnCounter)).unsqueeze(dim=0))).to(self.device).unsqueeze(dim=0)
            return self.resnet(modelInput.float(), useSigm=False, getConv=False), stateBudget - 1
            #return getValueOfState(currState, startingPlayer), stateBudget - 1

        validMoves = MinMaxAI.getValidMoves(currState, currPlayer)
        if len(validMoves) == 0:
            newState = copy.deepcopy(currState)
            newTurnCounter = copy.deepcopy(currTurnCounter)

            newState, newTurnCounter = LevelManager.incrementTurn(newState, newTurnCounter)
            return self.minimax(newState, newTurnCounter, currDepth, maxDepth, not isMaximizing, alpha, beta, currPlayer * -1, startingPlayer, stateBudget - 1)
        
        #random.shuffle(validMoves)

        for i in range(len(validMoves)):
            if MinMaxAI.isCreateOrCapture(currState, validMoves[i]):
                validMoves.insert(0, validMoves.pop(i))

        if isMaximizing:
            bestVal = -float("inf")
            for move in validMoves:
                stateBudget -= 1
                if stateBudget <= 0:
                    return None, -1
                
                childState = copy.deepcopy(currState)
                childTurnCounter = copy.deepcopy(currTurnCounter)

                childState, childTurnCounter = LevelManager.makeMove(childState, childTurnCounter, move)
                childState, childTurnCounter = LevelManager.incrementTurn(childState, childTurnCounter)

                util, stateBudget= self.minimax(childState, childTurnCounter, currDepth + 1, maxDepth, False, alpha, beta, currPlayer * -1, startingPlayer, stateBudget)

                if util == None or stateBudget <= 0:
                    return None, -1

                bestVal = max(bestVal, util)

                if bestVal > beta:
                    break

                alpha = max(alpha, bestVal)

            return bestVal, stateBudget
        else:
            bestVal = float("inf")
            for move in validMoves:
                stateBudget -= 1
                if stateBudget <= 0:
                    return None, -1
                
                childState = copy.deepcopy(currState)
                childTurnCounter = copy.deepcopy(currTurnCounter)

                childState, childTurnCounter = LevelManager.makeMove(childState, childTurnCounter, move)
                childState, childTurnCounter = LevelManager.incrementTurn(childState, childTurnCounter)

                util, stateBudget = self.minimax(childState, childTurnCounter, currDepth + 1, maxDepth, True, alpha, beta, currPlayer * -1, startingPlayer, stateBudget)

                if util == None or stateBudget <= 0:
                    return None, -1

                bestVal = min(bestVal, util)

                if bestVal < alpha:
                    break

                beta = min(beta, bestVal)

            return bestVal, stateBudget