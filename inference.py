from argparse import ArgumentParser

import torch
from torch.utils.data import DataLoader
from tqdm import tqdm

from pipeline.modules import TheModel
from pipeline.dataset import CustomDataset
from pipeline.utils import load_config, get_ids

def evaluate_result(res, save_path):
    ids = list(res.keys())
    preds = [res[i]['pred'] for i in ids]
    tars = [res[i]['tar'] for i in ids]

    with open(save_path, 'w') as f:
        for id in ids:
            pred = res[id]['pred']
            tar = res[id]['tar']
            f.write(f'{id} --> {pred} ({tar})\n')

    loss_func = torch.nn.BCELoss(reduction='sum')
    total_loss = loss_func(torch.Tensor(preds), torch.Tensor(tars))

    print(f'Total loss: {total_loss} (mean: {total_loss / len(ids)})')

def infer(opt, config):
    # Load model
    model = TheModel(config=config['model']).to(device='cuda')
    model.load_state_dict(torch.load(opt.model_path))
    model.eval()

    # Dataset & dataloader
    test_dataset = CustomDataset(
        ids=get_ids(opt.data_path),
        frames_path=opt.data_path,
        labels_path=opt.metadata_path,
        sampling=config['sampling'],
        img_size=config['input-size']
    )
    test_dataloader = DataLoader(test_dataset, batch_size=1, shuffle=False)

    # Loss function
    loss_func = torch.nn.BCELoss(reduction='sum')

    # Threshold
    thres = config['decision-strategy']['threshold']

    res = {}

    with torch.no_grad():
        for item in tqdm(test_dataloader):
            x, y, id = item
            x = x.to('cuda')
            y = torch.unsqueeze(y, 1).to(torch.float32).to('cuda')

            pred = model(x)
            
            res[id[0]] = {'pred': pred.item(), 'tar':y.item()}

    return res

if __name__ == '__main__':
    parser = ArgumentParser()

    parser.add_argument('--data_path')
    parser.add_argument('--metadata_path')
    parser.add_argument('--model_path')
    parser.add_argument('--save_path')

    opt = parser.parse_args()

    config = load_config(path='./config/train_config.json')

    res = infer(opt=opt, config=config)

    evaluate_result(res=res, save_path=opt.save_path)