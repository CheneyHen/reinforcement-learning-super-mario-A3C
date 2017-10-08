import tensorflow as tf
import numpy as np

GLOBAL_SCOPE = 'global'

# constant for actor loss
BETA = 0.01

class A3CNetwork(object):

    def __init__(self, state_shape, action_n, scope):
        
        self.action_n = action_n

        # worker-specific scope / 'global' scope
        with tf.variable_scope(scope):
            # state input placeholder
            state_maps = state_shape[2] if state_shape[2] else 1
            self.s = tf.placeholder(
                tf.float32, 
                shape=[None, state_shape[0], state_shape[1], state_maps],
                name='S'
            )

            # first part of network: CNN
            with tf.variable_scope('cnn'):
                self.layer1_conv = self.__new_conv_layer(
                    self.s,
                    input_channels_n=3,
                    filter_size=8,
                    feature_maps_n=16,
                    stride=4,
                    name='conv1'
                )
                self.layer2_conv = self.__new_conv_layer(
                    self.layer1_conv,
                    input_channels_n=16,
                    filter_size=4,
                    feature_maps_n=32,
                    stride=2,
                    name='conv2'
                )

                # get shape for the last convolution layer
                layer2_shape = self.layer2_conv.get_shape()

                # get height * width * feature_maps_n
                features_n = layer2_shape[1:].num_elements()

                # flatten into [None, features_n]
                self.layer2_out = tf.reshape(self.layer2_conv, [-1, features_n])

            with tf.variable_scope('ff1'):

                self.layer3_dense = tf.layers.dense(
                    self.layer2_out,
                    256,
                    activation=tf.nn.elu,
                    name='dense3',
                )

                # prepare as input for rnn by expanding dims to rank3
                self.layer3_out = tf.expand_dims(self.layer3_dense, [0])

            with tf.variable_scope('rnn'):
                # create lstm cell to use for RNN
                self.lstm_cell = tf.contrib.rnn.BasicLSTMCell(256,state_is_tuple=True)

                self.lstm_c = tf.placeholder(tf.float32, [1, self.lstm_cell.state_size.c])
                self.lstm_h = tf.placeholder(tf.float32, [1, self.lstm_cell.state_size.h])
                initial_state= tf.contrib.rnn.LSTMStateTuple(
                    self.lstm_c,
                    self.lstm_h
                )

                # TODO: sequence_length
                # Create RNN layer. Also, save lstm state for next training iteration
                self.layer4_lstm_output, self.layer4_lstm_state = tf.nn.dynamic_rnn(
                    self.lstm_cell, self.layer3_out, initial_state=initial_state,
                    time_major=False
                )

                self.layer4_out = tf.reshape(self.layer4_lstm_output, [-1, 256])

            # define the Actor network (policy)
            with tf.variable_scope('actor'):
                self.actor_out = tf.layers.dense(
                    self.layer4_out,
                    action_n,
                    activation=tf.nn.softmax,
                    name='actor_dense1'
                )

                
            # define the Critic network (value)
            with tf.variable_scope('critic'):
                self.critic_out = tf.layers.dense(
                    self.layer4_out,
                    1,
                    activation=None,
                    name='critic_dense1'
                )

            # only define loss functions for worker networks
            if scope != GLOBAL_SCOPE:
                
                with tf.variable_scope('loss'):

                    # the batch of rewards recieved
                    self.reward = tf.placeholder(tf.float32, shape=[None, 1], name='R')

                    # the action taken
                    self.action_taken = tf.placeholder(tf.float32, shape=[None, action_n])

                    # the log probability of taking action i given state. log(pi(a_i|s_i))
                    # The probability is extracted by multiplying by the one hot action vector
                    # add small number (1e-10) to prevent greedy epsilon policy from choosing
                    # and actin of probability zero. produces NaN otherwise
                    logp = tf.log(tf.reduce_sum(
                        self.actor_out * self.action_taken, axis=1, keep_dims=True
                    ) + 1e-10)
                    print('logp')
                    print(logp)

                    self.advantage = self.reward - self.critic_out
                    print('advantage')
                    print(self.advantage)

                    # calculate H(pi), the policy entropy. Add small number here aswell for the
                    # same reason as for logp
                    policy_entropy = -1 * tf.reduce_mean(self.actor_out * tf.log(self.actor_out + 1e-10))
                    print('entropy')
                    print(policy_entropy)

                    actor_loss = -1 * tf.reduce_mean(logp * self.advantage) \
                            + BETA * policy_entropy
                    print('actor loss')
                    print(actor_loss)

                    # loss function for Critic network
                    # multiplied by 1/2 because the learning rate is half
                    # of the Actor learning rate
                    critic_loss = 1/2 * tf.reduce_mean(tf.square(self.advantage))
                    print('critic_loss')
                    print(critic_loss)

                    self.loss = critic_loss + actor_loss


    def __new_conv_layer(self, inputs, input_channels_n, filter_size, feature_maps_n, stride, name):
        """ generate a new convolutional layer without any pooling attached

        """
                
        # filter weight shape
        shape = [filter_size, filter_size, input_channels_n, feature_maps_n]
                            
        # new filter weights and biases
        weights = tf.Variable(tf.truncated_normal(shape, stddev=0.05))
        biases = tf.Variable(tf.constant(0.05, shape=[feature_maps_n]))
        
        # new conv layer. stride 1, zero padding VALID
        layer = tf.nn.conv2d(
            input=inputs, 
            filter=weights, 
            strides=[1,stride,stride,1], 
            padding='VALID',
            name=name
        )
                                                        
        # add biases to each feature map
        layer += biases
                                                                                            
        # pass layer through an ELU
        layer = tf.nn.elu(layer)

        return layer

    def sync_global_network(self):
        """ use buffers of data from agent to update the global network """
        pass

    def copy_global(self):
        """ extract weights from the global network and copy to agent """
        pass

    # TODO: is epsilon greedy needed?
    def epsilon_greedy_action(self, sess, s, epsilon):
        """ perform action with exploration """
        if np.random.uniform() < epsilon:
            action = np.zeros(self.action_n,1)
            action[np.random.randint(0, len(self.action_n))] = 1
        else:
            action = self.sample_action(s)

        return action

    def sample_action(self, sess, s):
        """ perform optimal action """
        pass

if __name__ == '__main__':
    tf.reset_default_graph()
    a3cnet = A3CNetwork(256*256, 6, 'worker')
    print(a3cnet.layer1_conv)
    print(a3cnet.layer2_conv)
    print(a3cnet.layer2_out)
    print(a3cnet.layer3_dense)
    print(a3cnet.layer4_lstm_state)
    print(a3cnet.layer4_lstm_output)
    print(a3cnet.layer4_out)
    print(a3cnet.actor_out)
    print(a3cnet.critic_out)
