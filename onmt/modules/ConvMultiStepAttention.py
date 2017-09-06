import torch
import torch.nn as nn
import torch.nn.functional as F
from onmt.modules import aeq

scale_weight = 0.5 ** 0.5


def seq_linear(linear, x):
    batch, hidden_size, length, _ = x.size()
    h = linear(torch.transpose(x, 1, 2).contiguous().view(
        batch * length, hidden_size))
    return torch.transpose(h.view(batch, length, hidden_size, 1), 1, 2)


class ConvMultiStepAttention(nn.Module):
    def __init__(self, input_size):
        super(ConvMultiStepAttention, self).__init__()
        self.linear_in = nn.Linear(input_size, input_size)
        self.mask = None

    def applyMask(self, mask):
        self.mask = mask

    def forward(self, base_target_emb, input, encoder_out_t, encoder_out_c):
        """
        It's like Luong Attetion.
        Conv attention takes a key matrix, a value matrix and a query vector.
        Attention weight is calculated by key matrix with the query vector
        and sum on the value matrix. And the same operation is applied
        in each decode conv layer.
        Args:
            base_target_emb: target emb tensor
            input: output of decode conv
            encoder_out_t: the key matrix for calculation of attetion weight,
                which is the top output of encode conv
            encoder_out_c: the value matrix for the attention-weighted sum,
                which is the combination of base emb and top output of encode

        """
        # checks
        batch, channel, height, width = base_target_emb.size()
        batch_, channel_, height_, width_ = input.size()
        aeq(batch, batch_)
        aeq(height, height_)

        e_batch, e_channel, e_height = encoder_out_t.size()
        e_batch_, e_channel_, e_height_ = encoder_out_c.size()

        aeq(e_batch, e_batch_)
        aeq(e_height, e_height_)

        preatt = seq_linear(self.linear_in, input)
        target = (base_target_emb + preatt) * scale_weight
        target = torch.squeeze(target, 3)
        target = torch.transpose(target, 1, 2)
        pre_a = torch.bmm(target, encoder_out_t)

        if self.mask is not None:
            pre_a.data.masked_fill_(self.mask, -float('inf'))

        attn = F.softmax(pre_a)
        contextOutput = torch.bmm(attn, torch.transpose(encoder_out_c, 1, 2))
        contextOutput = torch.transpose(
            torch.unsqueeze(contextOutput, 3), 1, 2)
        return contextOutput, attn
