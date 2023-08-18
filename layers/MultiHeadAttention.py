from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


class MultiHeadAttention(nn.Module):
    """Multi Head Attention block from Attention is All You Need.

    Given 3 inputs of shape (batch_size, K, d_model), that will be used
    to compute query, keys and values, we output a self attention
    tensor of shape (batch_size, K, d_model).

    Parameters
    ----------
    d_model:
        Dimension of the input (and hence, also the output) vector.
    k:
        Dimension of all key matrix.
    q:
        Dimension of all query matrix.
    v:
        Dimension of all value matrix.
    h:
        Number of heads.
    dropout:
        Dropout ratio to be applied as float. If None, no dropout is applied
    discard_FC_before_MH:
        If set to True, there is no key transformation before, so the tanh is applied within the MH attention
    attention_size:
        Number of backward elements to apply attention.
        Deactivated if ``None``. Default is ``None``.
    """

    def __init__(self,
                 d_model: int,
                 k: int,
                 q: int,
                 v: int,
                 h: int,
                 dropout: float,
                 discard_FC_before_MH: bool,
                 **kwargs):
        """Initialize the Multi Head Block."""
        super().__init__()

        self._h = h
        self._k = k  # Needed for the scaled dot product attention
        self._discard_FC_before_MH = discard_FC_before_MH

        # Query, keys and value matrices
        self._W_q = nn.Linear(d_model, q*self._h)
        if not self._discard_FC_before_MH:
            self._W_k = nn.Linear(d_model, k*self._h)
        else:
            self._W_k = nn.Sequential(
                nn.Linear(d_model, k*self._h),
                nn.Tanh()
            )
        self._W_v = nn.Linear(d_model, v*self._h)

        # Output linear function
        self._W_o = nn.Linear(self._h*v, d_model)

        # Score placeholder
        self._scores = None

        # Dropout
        self._dropout = None
        if dropout is not None:
            self._dropout = nn.Dropout(p=dropout)

    def forward(self,
                query: torch.Tensor,
                key: torch.Tensor,
                value: torch.Tensor,
                mask: Optional[str] = None) -> torch.Tensor:
        """Propagate forward the input through the MHB.

        We compute for each head the queries, keys and values matrices,
        followed by the Scaled Dot-Product. The result is concatenated
        and returned with shape (batch_size, K, d_model).

        Parameters
        ----------
        query:
            Input tensor with shape (batch_size, 1, d_model) used to compute queries.
        key:
            Input tensor with shape (batch_size, T, d_model) used to compute keys.
        value:
            Input tensor with shape (batch_size, T, d_model) used to compute values.
        mask:
            Mask to apply on scores before computing attention.
            One of ``'subsequent'``, None. Default is None.

        Returns
        -------
            MH attention tensor with shape (batch_size, 1, d_model).
        """
        # Old version (works only as long as d_k = d_model):
        # K = key.shape[2]        #shape[1] corresponds to T, shape[2] corresponds to 2x GRU cells
        # After modifications (d_k = d_v = d_model/h in the multi-branch-attention) use self._k instead of K)

        # Compute Q, K and V, concatenate heads on batch dimension
        queries = torch.cat(self._W_q(query).chunk(self._h, dim=-1), dim=0)
        keys = torch.cat(self._W_k(key).chunk(self._h, dim=-1), dim=0)
        values = torch.cat(self._W_v(value).chunk(self._h, dim=-1), dim=0)

        # Scaled Dot Product
        self._scores = torch.bmm(queries, keys.transpose(1, 2)) / np.sqrt(self._k)

        # Apply sotfmax
        self._scores = F.softmax(self._scores, dim=-1)

        if self._dropout is not None:
            self._scores = self._dropout(self._scores)

        attention = torch.bmm(self._scores, values)

        # Concatenate the heads
        attention_heads = torch.cat(attention.chunk(self._h, dim=0), dim=-1)

        # Apply linear transformation W^O
        self_attention = self._W_o(attention_heads)

        return self_attention.squeeze()
