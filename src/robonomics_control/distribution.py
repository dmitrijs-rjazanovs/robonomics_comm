# -*- coding: utf-8 -*-
#
# Robonomics market distribution controller.
#

from robonomics_market.signer import bidhash
from robonomics_market.msg import Bid
from web3 import Web3, HTTPProvider
from std_msgs.msg import String
from std_srvs.srv import Empty, EmptyResponse
import rospy
import json
import numpy as np

def desired_distribution(cap_vector, rob_vector):
    '''
        Desired robot distribution according to investor capital distribution,
        ref http://ensrationis.com/smart-factory-and-capital/
    '''
    return cap_vector * (sum(rob_vector) + 1) / sum(cap_vector)

def distribution_error(cap_vector, rob_vector):
    '''
        Robot distribution error according to current capital and robot distribution,
        ref http://ensrationis.com/smart-factory-and-capital/
    '''
    return desired_distribution(cap_vector, rob_vector) - rob_vector

class Distribution:
    robots = {}

    def __init__(self):
        '''
            Market distribution node initialisation.
        '''
        rospy.init_node('robonomics_distribution')

        http_provider = rospy.get_param('~web3_http_provider')
        self.web3 = Web3(HTTPProvider(http_provider))

        investors_abi = json.loads(rospy.get_param('~investors_contract_abi'))
        investors_address = rospy.get_param('~investors_contract_address')
        self.investors = self.web3.eth.contract(investors_address, abi=investors_abi)

        self.market_list = json.loads(rospy.get_param('~supported_models'))

        for m in self.market_list:
            self.robots[m] = set()

        self.market = rospy.Publisher('current', String, queue_size=10)
        self.subscribe_new_bids()

        rospy.Service('reset', Empty, self.reset)

    def spin(self):
        '''
            Waiting for the new messages.
        '''
        rospy.sleep(3)
        self.update_current_market()
        rospy.spin()

    def subscribe_new_bids(self):
        '''
            Subscribe to incoming bids and register new robots by markets.
        '''
        def ecrecover(msg):
            return self.web3.eth.account.recoverMessage(data=bidhash(msg),
                                                        signature=msg.signature)

        def incoming_bid(msg):
            if msg.model in self.market_list:
                robot_id = ecrecover(msg)
                # Clean up robot from another markets
                self.robots = {k: v - set([robot_id]) for k, v in self.robots.items()}

                # Append robot to current market
                self.robots[msg.model].add(robot_id)
                rospy.loginfo('Robots updated: %s', self.robots)

                self.update_current_market()

        rospy.Subscriber('market/incoming/bid', Bid, incoming_bid)

    def update_current_market(self):
        '''
            Market distribution control rule.
            Choose market by capital proportional robot distribution,
            ref http://ensrationis.com/smart-factory-and-capital/
        '''
        rospy.loginfo('Input market list is %s', self.market_list)

        cap = [self.investors.call().supply(m) for m in self.market_list]
        rospy.loginfo('Capitalization vector is %s', cap)

        rob = [len(self.robots[m]) for m in self.market_list]
        rospy.loginfo('Real robot distribution is %s', rob)

        err = distribution_error(np.array(cap), np.array(rob))
        rospy.loginfo('Robot distribution error is %s', err)

        maxi = np.argmax(err)
        rospy.loginfo('Maximal error index is %d', maxi)

        self.market.publish(self.market_list[maxi])

    def reset(self, request):
        rospy.loginfo('Robot distribution reset')
        self.robots = {}
        for m in self.market_list:
            self.robots[m] = set()
        self.update_current_market()
        return EmptyResponse()
