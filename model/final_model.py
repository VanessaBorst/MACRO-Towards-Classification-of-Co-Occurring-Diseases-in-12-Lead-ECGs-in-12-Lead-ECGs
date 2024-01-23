import torch.nn as nn
from torchinfo import summary

from base import BaseModel
from layers.BasicBlock1dWithNorm import BasicBlock1dWithNorm
from layers.BasicBlock1dWithNormPreActivationDesign import BasicBlock1dWithNormPreactivation
from layers.ContextualAttention import MultiHeadContextualAttention, MultiHeadContextualAttentionV2, \
    MultiHeadContextualAttentionV3, MultiHeadContextualAttentionV4, MultiHeadContextualAttentionV5


class FinalModel(BaseModel):
    def __init__(self, apply_final_activation, multi_label_training, input_channel=12, num_classes=9,
                 drop_out_first_conv_blocks=0.2, drop_out_second_conv_blocks=0.2,
                 drop_out_gru=0.2, dropout_last_bn=0.2,
                 mid_kernel_size_first_conv_blocks=3, mid_kernel_size_second_conv_blocks=3,
                 last_kernel_size_first_conv_blocks=24, last_kernel_size_second_conv_blocks=48,
                 stride_first_conv_blocks=2, stride_second_conv_blocks=2,
                 down_sample="conv", vary_channels=True, pos_skip="not_last",
                 norm_type="BN", norm_pos="all", norm_before_act=True,
                 use_pre_activation_design=True, use_pre_conv=True,
                 pre_conv_kernel=16,
                 gru_units=12, dropout_attention=0.2, heads=3,
                 discard_FC_before_MH=False,
                 use_reduced_head_dims=None,
                 attention_activation_function=None,
                 attention_type="v2"):
        """
        :param apply_final_activation: whether the Sigmoid(sl) or the LogSoftmax(ml) should be applied at the end
        :param multi_label_training: if true, Sigmoid is used as final activation, else the LogSoftmax
        :param num_classes: Num of classes to classify
        :param num_cnn_blocks: Num of CNN blocks to use
        """
        super().__init__()
        self._apply_final_activation = apply_final_activation

        assert down_sample == "conv" or down_sample == "max_pool" or down_sample == "avg_pool", \
            "Downsampling should either be conv or max_pool or avg_pool"

        assert use_reduced_head_dims is None or attention_type == "v1", \
            "use_reduced_head_dims can only be used with attention_type=v1!"

        assert attention_activation_function is None or attention_type == "v1", \
            "attention_activation_function can only be used with attention_type=v1!"

        if use_reduced_head_dims:
            assert (2 * gru_units) % heads == 0, \
                "Twice the number of GRU cells (d_model) must be divisible by num_heads!"

        if use_pre_activation_design:
            assert pos_skip == "all" or pos_skip == "not_last", "For the preactivation design, ''not first'' is no valid" \
                                                                "option for the skip connections! Choose between ''all'' " \
                                                                "and ''not last''"
        else:
            # assert use_pre_conv is None or use_pre_conv is False, "Pre-Conv not possible without pre-activation design"
            assert norm_before_act is None or norm_before_act is True, "Norm after activation not possible without " \
                                                                       "preactivation design"

        self._pos_skip = pos_skip
        self._use_pre_conv = use_pre_conv
        self._use_pre_activation_design = use_pre_activation_design

        if vary_channels:
            out_channel_block_1 = 24
            out_channel_block_2 = 48
            out_channel_block_3 = 48
            out_channel_block_4 = 24
            out_channel_block_5 = 12
        else:
            out_channel_block_1 = out_channel_block_2 = out_channel_block_3 \
                = out_channel_block_4 = out_channel_block_5 = 12

        if use_pre_activation_design and use_pre_conv:
            # Start with a convolution with stride 1, which keeps the channel amount constant
            if norm_type == "BN":
                starting_norm = nn.BatchNorm1d(num_features=input_channel)
            elif norm_type == "IN":
                starting_norm = nn.InstanceNorm1d(num_features=input_channel, affine=True)
            if norm_before_act:
                self._starting_conv = nn.Sequential(
                    nn.Conv1d(in_channels=input_channel, out_channels=input_channel, kernel_size=pre_conv_kernel),
                    starting_norm,
                    nn.LeakyReLU(0.3)
                )
            else:
                self._starting_conv = nn.Sequential(
                    nn.Conv1d(in_channels=input_channel, out_channels=input_channel, kernel_size=pre_conv_kernel),
                    nn.LeakyReLU(0.3),
                    starting_norm
                )

        if use_pre_activation_design:
            self._first_conv_block_1 = BasicBlock1dWithNormPreactivation(in_channels=input_channel,
                                                                         out_channels=out_channel_block_1,
                                                                         mid_kernels_size=mid_kernel_size_first_conv_blocks,
                                                                         last_kernel_size=last_kernel_size_first_conv_blocks,
                                                                         stride=stride_first_conv_blocks,
                                                                         down_sample=down_sample,
                                                                         drop_out=drop_out_first_conv_blocks,
                                                                         norm_type=norm_type, norm_pos=norm_pos,
                                                                         norm_before_act=norm_before_act)

            self._first_conv_block_2 = BasicBlock1dWithNormPreactivation(in_channels=out_channel_block_1,
                                                                         out_channels=out_channel_block_2,
                                                                         mid_kernels_size=mid_kernel_size_first_conv_blocks,
                                                                         last_kernel_size=last_kernel_size_first_conv_blocks,
                                                                         stride=stride_first_conv_blocks,
                                                                         down_sample=down_sample,
                                                                         drop_out=drop_out_first_conv_blocks,
                                                                         norm_type=norm_type, norm_pos=norm_pos,
                                                                         norm_before_act=norm_before_act)
            self._first_conv_block_3 = BasicBlock1dWithNormPreactivation(in_channels=out_channel_block_2,
                                                                         out_channels=out_channel_block_3,
                                                                         mid_kernels_size=mid_kernel_size_first_conv_blocks,
                                                                         last_kernel_size=last_kernel_size_first_conv_blocks,
                                                                         stride=stride_first_conv_blocks,
                                                                         down_sample=down_sample,
                                                                         drop_out=drop_out_first_conv_blocks,
                                                                         norm_type=norm_type, norm_pos=norm_pos,
                                                                         norm_before_act=norm_before_act)
            self._first_conv_block_4 = BasicBlock1dWithNormPreactivation(in_channels=out_channel_block_3,
                                                                         out_channels=out_channel_block_4,
                                                                         mid_kernels_size=mid_kernel_size_first_conv_blocks,
                                                                         last_kernel_size=last_kernel_size_first_conv_blocks,
                                                                         stride=stride_first_conv_blocks,
                                                                         down_sample=down_sample,
                                                                         drop_out=drop_out_first_conv_blocks,
                                                                         norm_type=norm_type, norm_pos=norm_pos,
                                                                         norm_before_act=norm_before_act)

            # Second Type of Conv Blocks
            if pos_skip == "all":
                self._second_conv_block_1 = BasicBlock1dWithNormPreactivation(in_channels=out_channel_block_4,
                                                                              out_channels=out_channel_block_5,
                                                                              mid_kernels_size=mid_kernel_size_second_conv_blocks,
                                                                              last_kernel_size=last_kernel_size_second_conv_blocks,
                                                                              stride=stride_second_conv_blocks,
                                                                              down_sample=down_sample,
                                                                              drop_out=drop_out_second_conv_blocks,
                                                                              norm_type=norm_type, norm_pos=norm_pos,
                                                                              norm_before_act=norm_before_act)
            elif pos_skip == "not_last":
                # Use the normal block without pre-activation and deactivate the skip connections
                # Attention: This must be handled in the forward, since the normal block exspects a single
                # input value, but the pre-activation block output a tuple (out, residuals)
                self._second_conv_block_1 = BasicBlock1dWithNorm(in_channels=out_channel_block_4,
                                                                 out_channels=out_channel_block_5,
                                                                 mid_kernels_size=mid_kernel_size_second_conv_blocks,
                                                                 last_kernel_size=last_kernel_size_second_conv_blocks,
                                                                 stride=stride_second_conv_blocks,
                                                                 down_sample=down_sample,
                                                                 drop_out=drop_out_second_conv_blocks,
                                                                 skips_active=False,
                                                                 norm_type=norm_type, norm_pos=norm_pos)

        else:
            if pos_skip == "all" or pos_skip == "not_last":
                self._first_conv_block_1 = BasicBlock1dWithNorm(in_channels=input_channel,
                                                                out_channels=out_channel_block_1,
                                                                mid_kernels_size=mid_kernel_size_first_conv_blocks,
                                                                last_kernel_size=last_kernel_size_first_conv_blocks,
                                                                stride=stride_first_conv_blocks,
                                                                down_sample=down_sample,
                                                                drop_out=drop_out_first_conv_blocks,
                                                                skips_active=True,
                                                                norm_type=norm_type, norm_pos=norm_pos)
            elif pos_skip == "not_first":
                self._first_conv_block_1 = BasicBlock1dWithNorm(in_channels=input_channel,
                                                                out_channels=out_channel_block_1,
                                                                mid_kernels_size=mid_kernel_size_first_conv_blocks,
                                                                last_kernel_size=last_kernel_size_first_conv_blocks,
                                                                stride=stride_first_conv_blocks,
                                                                down_sample=down_sample,
                                                                drop_out=drop_out_first_conv_blocks,
                                                                skips_active=False,
                                                                norm_type=norm_type, norm_pos=norm_pos)

            self._first_conv_block_2 = BasicBlock1dWithNorm(in_channels=out_channel_block_1,
                                                            out_channels=out_channel_block_2,
                                                            mid_kernels_size=mid_kernel_size_first_conv_blocks,
                                                            last_kernel_size=last_kernel_size_first_conv_blocks,
                                                            stride=stride_first_conv_blocks,
                                                            down_sample=down_sample,
                                                            drop_out=drop_out_first_conv_blocks,
                                                            skips_active=True,
                                                            norm_type=norm_type, norm_pos=norm_pos)
            self._first_conv_block_3 = BasicBlock1dWithNorm(in_channels=out_channel_block_2,
                                                            out_channels=out_channel_block_3,
                                                            mid_kernels_size=mid_kernel_size_first_conv_blocks,
                                                            last_kernel_size=last_kernel_size_first_conv_blocks,
                                                            stride=stride_first_conv_blocks,
                                                            down_sample=down_sample,
                                                            drop_out=drop_out_first_conv_blocks,
                                                            skips_active=True,
                                                            norm_type=norm_type, norm_pos=norm_pos)
            self._first_conv_block_4 = BasicBlock1dWithNorm(in_channels=out_channel_block_3,
                                                            out_channels=out_channel_block_4,
                                                            mid_kernels_size=mid_kernel_size_first_conv_blocks,
                                                            last_kernel_size=last_kernel_size_first_conv_blocks,
                                                            stride=stride_first_conv_blocks,
                                                            down_sample=down_sample,
                                                            drop_out=drop_out_first_conv_blocks,
                                                            skips_active=True,
                                                            norm_type=norm_type, norm_pos=norm_pos)

            # Second Type of Conv Blocks
            if pos_skip == "all" or pos_skip == "not_first":
                self._second_conv_block_1 = BasicBlock1dWithNorm(in_channels=out_channel_block_4,
                                                                 out_channels=out_channel_block_5,
                                                                 mid_kernels_size=mid_kernel_size_second_conv_blocks,
                                                                 last_kernel_size=last_kernel_size_second_conv_blocks,
                                                                 stride=stride_second_conv_blocks,
                                                                 down_sample=down_sample,
                                                                 drop_out=drop_out_second_conv_blocks,
                                                                 skips_active=True,
                                                                 norm_type=norm_type, norm_pos=norm_pos)
            elif pos_skip == "not_last":
                self._second_conv_block_1 = BasicBlock1dWithNorm(in_channels=out_channel_block_4,
                                                                 out_channels=out_channel_block_5,
                                                                 mid_kernels_size=mid_kernel_size_second_conv_blocks,
                                                                 last_kernel_size=last_kernel_size_second_conv_blocks,
                                                                 stride=stride_second_conv_blocks,
                                                                 down_sample=down_sample,
                                                                 drop_out=drop_out_second_conv_blocks,
                                                                 skips_active=False,
                                                                 norm_type=norm_type, norm_pos=norm_pos)

        # Without last option the input would have to be (seq_len, batch, input_size)
        # With batch_first it can be of the shape (batch, seq_len, input/feature_size)
        # input_size = feature_size per timestamp outputted by the CNNs
        # hidden_size = gru_hidden_dim
        self._biGRU = nn.GRU(input_size=out_channel_block_5, hidden_size=gru_units,
                             num_layers=1, bidirectional=True, batch_first=True)

        self._biGru_activation_do = nn.Sequential(
            nn.LeakyReLU(0.3),
            nn.Dropout(drop_out_gru)
        )

        match attention_type:
            case "v1":
                # Own MHA implementation with random query initialization
                head_dims = use_reduced_head_dims if use_reduced_head_dims is not None else False
                attention_activation = attention_activation_function if attention_activation_function is not None else "softmax"
                self._multi_head_contextual_attention = MultiHeadContextualAttention(d_model=2 * gru_units,
                                                                                     dropout=dropout_attention,
                                                                                     heads=heads,
                                                                                     discard_FC_before_MH=discard_FC_before_MH,
                                                                                     use_reduced_head_dims=head_dims,
                                                                                     attention_activation_function=attention_activation)
            case "v2":
                # Torch MHA implementation with random query initialization
                self._multi_head_contextual_attention = MultiHeadContextualAttentionV2(d_model=2 * gru_units,
                                                                                       dropout=dropout_attention,
                                                                                       heads=heads,
                                                                                       discard_FC_before_MH=discard_FC_before_MH)
            case "v3":
                # Torch MHA implementation +  buggy query initialization based on the mean of the BiGRU output
                self._multi_head_contextual_attention = MultiHeadContextualAttentionV3(d_model=2 * gru_units,
                                                                                       dropout=dropout_attention,
                                                                                       heads=heads,
                                                                                       discard_FC_before_MH=discard_FC_before_MH)
            case "v4":
                # Torch MHA implementation +  Learnable query projection with Linear layer
                self._multi_head_contextual_attention = MultiHeadContextualAttentionV4(d_model=2 * gru_units,
                                                                                       dropout=dropout_attention,
                                                                                       heads=heads,
                                                                                       discard_FC_before_MH=discard_FC_before_MH)
            case "v5":
                # Torch MHA implementation +  Method "initialize_weights()" for query initialization
                self._multi_head_contextual_attention = MultiHeadContextualAttentionV5(d_model=2 * gru_units,
                                                                                       dropout=dropout_attention,
                                                                                       heads=heads,
                                                                                       discard_FC_before_MH=discard_FC_before_MH)
            case _:
                raise ValueError(f"Attention type {attention_type} not supported!")

        self._batchNorm = nn.Sequential(
            # The batch normalization layer has 24*2=48 trainable and 24*2=48 non-trainable parameters
            nn.BatchNorm1d(gru_units * 2),
            nn.LeakyReLU(0.3),
            nn.Dropout(dropout_last_bn)
        )

        self._fcn = nn.Linear(in_features=gru_units * 2, out_features=num_classes)

        if apply_final_activation:
            self._final_activation = nn.Sigmoid() if multi_label_training else nn.LogSoftmax(dim=1)

    def forward(self, x):
        if self._use_pre_activation_design:
            if self._use_pre_conv:
                x = self._starting_conv(x)
            # Start with the residual blocks
            x = self._first_conv_block_1((x, x))
            x = self._first_conv_block_2(x)
            x = self._first_conv_block_3(x)
            x = self._first_conv_block_4(x)
            # The last block needs to be handled separately, depending if skips should be used as well
            if self._pos_skip == "all":
                x = self._second_conv_block_1(x)
            elif self._pos_skip == "not_last":
                x, residuals = x
                x = self._second_conv_block_1(x)

            # If the last block uses skips, it return a tuple
            if self._pos_skip == "all":
                x, residuals = x
        else:
            x = self._first_conv_block_1(x)
            x = self._first_conv_block_2(x)
            x = self._first_conv_block_3(x)
            x = self._first_conv_block_4(x)
            x = self._second_conv_block_1(x)

        x = x.permute(0, 2, 1)  # switch seq_length and feature_size for the BiGRU
        x, last_hidden_state = self._biGRU(x)
        x = self._biGru_activation_do(x)
        x = self._multi_head_contextual_attention(x)
        x = self._batchNorm(x)
        x = self._fcn(x)
        if self._apply_final_activation:
            return self._final_activation(x)
        else:
            return x


if __name__ == "__main__":
    model = FinalModel(apply_final_activation=False,
                       multi_label_training=True,
                       down_sample="conv",
                       vary_channels=True,
                       pos_skip="all",
                       norm_before_act=True,
                       norm_pos="all",
                       norm_type="BN",
                       use_pre_activation_design=True,
                       use_pre_conv=True,
                       pre_conv_kernel=16,
                       discard_FC_before_MH=False,
                       dropout_attention=0.3,
                       gru_units=32,
                       heads=16)
    #print(str(model))
    summary(model, input_size=(2, 12, 72000), col_names=["input_size", "output_size", "kernel_size", "num_params"])
