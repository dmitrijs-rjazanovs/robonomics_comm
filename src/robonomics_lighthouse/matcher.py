# -*- coding: utf-8 -*-
#
# Robonomics market Bid/Ask matcher node. 
#

from robonomics_lighthouse.msg import Bid, Ask
from web3 import Web3, HTTPProvider
from base58 import b58decode
from binascii import hexlify
import rospy, json

from . import signer 


class Matcher:
    bids = {}
    asks = {}

    def __init__(self):
        '''
            Market market matcher initialisation.
        '''
        rospy.init_node('robonomics_matcher')

        http_provider = rospy.get_param('~web3_http_provider')
        self.web3 = Web3(HTTPProvider(http_provider))

        builder_abi = json.loads(rospy.get_param('~builder_abi'))
        builder_address = rospy.get_param('~builder_contract')
        self.builder = self.web3.eth.contract(builder_address, abi=builder_abi)

        self.account = rospy.get_param('~eth_account_address', self.web3.eth.accounts[0])

        rospy.Subscriber('infochan/incoming/bid', Bid, lambda x: self.match(bid=x))
        rospy.Subscriber('infochan/incoming/ask', Ask, lambda x: self.match(ask=x))

    def spin(self):
        '''
            Waiting for the new messages.
        '''
        rospy.spin()

    def match(self, bid=None, ask=None):
        '''
            Make bids and asks intersection.
        '''
        assert(not bid or not ask)

        if not ask:
            h = hash((bid.model, bid.token, bid.cost, bid.count))
            if h in self.bids:
                self.bids[h].append(bid)
            else:
                self.bids[h] = [bid]
        else:
            h = hash((ask.model, ask.token, ask.cost, ask.count))
            if h in self.asks:
                self.asks[h].append(ask)
            else:
                self.asks[h] = [ask]

        prlot = lambda lot: '| {0} Mod: {1} Cst: {2} Cnt: {3} |'.format(
                            'Ask Obj: '+lot.objective if hasattr(lot, 'objective') else 'Bid',
                            lot.model, lot.cost, lot.count)

        try:
            if not ask:
                h = hash((bid.model, bid.token, bid.cost, bid.count))
                ask = self.asks[h].pop()
                bid = self.bids[h].pop()
            else:
                h = hash((ask.model, ask.token, ask.cost, ask.count))
                bid = self.bids[h].pop()
                ask = self.asks[h].pop()

            rospy.loginfo('Matched %s & %s', prlot(ask), prlot(bid))
            self.new_liability(ask, bid)

        except (KeyError, IndexError):
            rospy.loginfo('No match for: %s', prlot(ask or bid))


    def new_liability(self, ask, bid):
        '''
            Create liability contract for matched ask & bid.
        '''
        exps = [ ask.cost * ask.count, bid.lighthouseFee, ask.validatorFee ]
        sign = [ ask.salt
               , bytes(31) + bytes([ask.signature[64]])
               , ask.signature[0:32]
               , ask.signature[32:64]
               , bid.salt
               , bytes(31) + bytes([bid.signature[64]])
               , bid.signature[0:32]
               , bid.signature[32:64] ]
        deadline = [ ask.deadline, bid.deadline ]
        self.builder.transact({'gas': 1000000, 'from': self.account}).createLiability(
                b58decode(ask.model)[2:],
                b58decode(ask.objective)[2:],
                ask.token,
                ask.validator,
                exps, sign, deadline)
        rospy.loginfo('Liability contract created')
